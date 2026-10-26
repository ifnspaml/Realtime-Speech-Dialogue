"""Serialize explicit model replacement inside one persistent GPU allocation."""
import argparse
import fcntl
import json
import os
import signal
import socket
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('moshi', 'nemotron')


def atomic_json(path, value):
    """Publish complete state/request files for concurrent UI and supervisor reads."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex)
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def request_model(directory, model, *, restart=False):
    """Queue an operator request; the GPU-owning supervisor performs replacement."""
    if model not in MODELS:
        raise ValueError('Unknown end-to-end model')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    request = {'model': model, 'generation': uuid.uuid4().hex, 'requested_at': time.time(),
               'restart': restart}
    atomic_json(directory / 'request.json', request)
    return request


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def stop_group(process, timeout=20):
    """Kill the full process group, including container and codec children."""
    if process is None:
        return
    for sig, seconds in ((signal.SIGTERM, timeout), (signal.SIGKILL, 5)):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.1)
    process.wait(timeout=5)


class Supervisor:
    """Own one model process group and its warmup client on one Slurm GPU."""
    def __init__(self, directory, commands=None, memory=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.commands = commands or {name: ['bash', str(ROOT / 'scripts' / ('launch_' + name + '_slot.sh'))] for name in MODELS}
        self.memory = memory or self.gpu_memory
        self.process = None
        self.probe = None
        self.log = None
        self.state = {'state': 'UNLOADED', 'model': None, 'job_id': os.environ.get('SLURM_JOB_ID')}
        self.baseline = self.memory()
        self.state['idle_memory_mib'] = self.baseline
        self.publish()

    def gpu_memory(self):
        device = os.environ.get('CUDA_VISIBLE_DEVICES', '').split(',')[0]
        if not device:
            raise RuntimeError('Slurm must expose one allocated GPU')
        return int(subprocess.check_output(['nvidia-smi', '-i', device, '--query-gpu=memory.used', '--format=csv,noheader,nounits'], text=True).strip())

    def publish(self, **fields):
        self.state.update(fields, updated_at=time.time())
        atomic_json(self.directory / 'state.json', self.state)

    def unload(self):
        """Release every child and check VRAM before another heavyweight load."""
        self.publish(state='STOPPING')
        stop_group(self.probe)
        self.probe = None
        stop_group(self.process)
        self.process = None
        if self.log:
            self.log.close()
            self.log = None
        deadline = time.monotonic() + 30
        while self.memory() > self.baseline + 256:
            if time.monotonic() >= deadline:
                raise RuntimeError('GPU memory did not return to idle; refusing to load another model')
            time.sleep(1)
        self.publish(state='UNLOADED', model=None, idle_after_stop_mib=self.memory())

    def replace(self, request):
        """Reuse a healthy matching process unless an explicit restart is requested."""
        model = request['model']
        if model not in MODELS:
            raise ValueError('Invalid requested model')
        if self.state.get('model') == model and self.process and self.process.poll() is None and not request.get('restart', False):
            self.publish(last_request_generation=request['generation'])
            return False
        self.unload()
        generation = request['generation']
        self.publish(state='LOADING', model=model, generation=generation, started_at=time.time(), error=None)
        self.log = (self.directory / (generation + '.log')).open('w')
        environment = dict(os.environ, VOICE_DEMO_SLOT_RUN=str(self.directory / generation))
        Path(environment['VOICE_DEMO_SLOT_RUN']).mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen(self.commands[model], cwd=ROOT, env=environment, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
        return True

    def tick(self):
        """Advance startup from a listening port to a verified streaming response."""
        if not self.process:
            return
        if self.process.poll() is not None:
            raise RuntimeError('Model process exited: ' + str(self.process.returncode))
        if time.time() - self.state['updated_at'] > 20:
            self.publish()
        if self.state['state'] == 'READY':
            return
        if time.time() - self.state['started_at'] > 1800:
            raise RuntimeError('Model startup or inference validation exceeded 30 minutes')
        model = self.state['model']
        port = int(os.environ.get('MOSHI_PORT', '8998')) if model == 'moshi' else int(os.environ.get('NIM_HTTP_API_PORT', '9000'))
        if self.probe is None:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    pass
            except OSError:
                return
            directory = self.directory / self.state['generation'] / 'validation'
            python = os.environ.get('VOICE_DEMO_TOOLS_PYTHON', str(ROOT / '.venv-tools/bin/python'))
            if model == 'moshi':
                command = [python, 'scripts/moshi_wav.py', '--native', '--url', f'ws://127.0.0.1:{port}/api/chat']
            else:
                command = [python, 'scripts/realtime_wav.py', '--backend', 'nemotron', '--url', f'ws://127.0.0.1:{port}/v1/realtime', '--total-timeout', '300']
            command += ['--wav', str(Path(os.environ.get('VOICE_DEMO_STARTUP_WAV', ROOT / 'artifacts/input/short.wav'))), '--output', str(directory)]
            self.probe = subprocess.Popen(command, cwd=ROOT, stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)
            self.publish(state='WARMING')
        elif self.probe.poll() is not None:
            summary = read_json(self.directory / self.state['generation'] / 'validation/summary.json', {})
            if self.probe.returncode != 0 or summary.get('status') != 'PASS':
                raise RuntimeError('Real WAV startup validation failed; see generation log')
            # PASS certifies streamed text/nonzero audio, not answer quality.
            self.publish(state='READY', startup_seconds=time.time() - self.state['started_at'], memory_mib=self.memory())

    def close(self):
        self.unload()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(os.environ.get('VOICE_DEMO_SLOT_DIRECTORY', ROOT / 'runtime/end-to-end')))
    parser.add_argument('--initial', choices=MODELS, default='moshi')
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    with (args.directory / 'supervisor.lock').open('w') as lock:
        # Only one owner may replace processes or publish state in this slot.
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        supervisor = Supervisor(args.directory)
        # A new allocation starts with the requested initial model (default
        # Moshi), rather than replaying a stale request from an earlier job.
        request_model(args.directory, args.initial)
        stopped = False
        def stop(*_):
            nonlocal stopped
            stopped = True
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        handled = None
        try:
            while not stopped:
                request = read_json(args.directory / 'request.json')
                try:
                    if request and request.get('generation') != handled:
                        handled = request['generation']
                        supervisor.replace(request)
                    supervisor.tick()
                except Exception as error:
                    try:
                        supervisor.unload()
                    except Exception as cleanup_error:
                        supervisor.publish(state='FAILED', error=str(error) + '; cleanup: ' + str(cleanup_error), generation=handled)
                        raise
                    supervisor.publish(state='FAILED', error=str(error), generation=handled)
                time.sleep(1)
        finally:
            supervisor.close()


if __name__ == '__main__':
    main()
