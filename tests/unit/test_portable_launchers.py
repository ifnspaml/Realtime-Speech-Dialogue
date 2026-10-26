#!/usr/bin/env python3
"""CPU-only checks for portable launcher defaults and fail-fast behavior."""
from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def run_bash(script: str, env: dict | None = None, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    # Avoid inheriting personal overrides from the caller environment.
    for key in list(merged):
        if key.startswith("VOICE_DEMO_") or key in {
            "HF_HOME",
            "HF_HUB_CACHE",
            "TORCH_HOME",
            "NLTK_DATA",
            "UV_CACHE_DIR",
            "MOSHI_HOST",
            "MOSHI_PORT",
            "PLAYWRIGHT_BROWSERS_PATH",
            "NEMOTRON_MODEL_DIR",
        }:
            merged.pop(key, None)
    if env:
        merged.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        cwd=str(ROOT),
        env=merged,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


class PortableCommonTests(unittest.TestCase):
    def test_common_defaults_are_project_local(self) -> None:
        proc = run_bash(
            textwrap.dedent(
                f"""
                source "{SCRIPTS}/common.sh"
                printf '%s\\n' "$VOICE_DEMO_ROOT"
                printf '%s\\n' "$VOICE_DEMO_TOOLS_PYTHON"
                printf '%s\\n' "$VOICE_DEMO_BACKEND_PYTHON"
                printf '%s\\n' "$VOICE_DEMO_MOSHI_PYTHON"
                printf '%s\\n' "$HF_HOME"
                printf '%s\\n' "$TORCH_HOME"
                printf '%s\\n' "$NLTK_DATA"
                printf '%s\\n' "$UV_CACHE_DIR"
                printf '%s\\n' "$HF_S2S_REPO"
                printf '%s\\n' "$UV_LINK_MODE"
                """
            )
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(lines[0], str(ROOT))
        self.assertTrue(lines[1].startswith(str(ROOT)))
        self.assertIn(".venv-tools/bin/python", lines[1])
        self.assertIn(".venv-modular/bin/python", lines[2])
        self.assertIn(".venv-moshi/bin/python", lines[3])
        self.assertEqual(lines[4], f"{ROOT}/models/huggingface")
        self.assertEqual(lines[5], f"{ROOT}/models/torch")
        self.assertEqual(lines[6], f"{ROOT}/models/nltk_data")
        self.assertEqual(lines[7], f"{ROOT}/.cache/uv")
        self.assertEqual(lines[8], f"{ROOT}/third_party/hf-speech-to-speech")
        self.assertEqual(lines[9], "copy")
        for value in lines[1:9]:
            self.assertTrue(
                value == str(ROOT) or value.startswith(str(ROOT) + os.sep),
                f"default escapes project root: {value}",
            )
            self.assertNotRegex(value, r"(^|:)/home/[^/]+/")

    def test_env_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "custom.env"
            env_file.write_text('export VOICE_DEMO_MODULAR_PORT="5555"\n', encoding="utf-8")
            proc = run_bash(
                textwrap.dedent(
                    f"""
                    unset VOICE_DEMO_MODULAR_PORT
                    export VOICE_DEMO_ENV_FILE="{env_file}"
                    source "{SCRIPTS}/common.sh"
                    printf '%s\\n' "$VOICE_DEMO_MODULAR_PORT"
                    """
                )
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout.strip(), "5555")


class SetupScopeTests(unittest.TestCase):
    def test_setup_help_mentions_explicit_backends(self) -> None:
        proc = run_bash(f'bash "{SCRIPTS}/setup.sh" --help')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--modular", proc.stdout)
        self.assertIn("--moshi", proc.stdout)
        self.assertIn("no model downloads", proc.stdout.lower())


class FailFastLaunchTests(unittest.TestCase):
    def test_ui_only_launcher_drops_real_backend_routes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            py = Path(tmp) / "python"
            py.write_text('#!/bin/bash\nprintf "%s|%s|%s|%s" "${VOICE_DEMO_MODULAR_URL-unset}" "${VOICE_DEMO_MOSHI_URL-unset}" "${VOICE_DEMO_NEMOTRON_URL-unset}" "${VOICE_DEMO_SLOT_CONTROL-unset}"\n')
            py.chmod(0o700)
            proc = run_bash(f'bash "{SCRIPTS}/run_mock.sh"', env={
                "VOICE_DEMO_TOOLS_PYTHON": str(py), "VOICE_DEMO_MODULAR_URL": "ws://example.invalid/modular",
                "VOICE_DEMO_MOSHI_URL": "ws://example.invalid/moshi", "VOICE_DEMO_NEMOTRON_URL": "ws://example.invalid/nemotron",
                "VOICE_DEMO_SLOT_CONTROL": "1"})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "unset|unset|unset|unset")

    def test_run_moshi_fails_without_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "empty-snap"
            snap.mkdir()
            py = Path(tmp) / "python"
            py.write_text("#!/bin/bash\necho unexpected-download >&2\nexit 99\n", encoding="utf-8")
            py.chmod(py.stat().st_mode | stat.S_IEXEC)
            proc = run_bash(
                f'bash "{SCRIPTS}/run_moshi.sh"',
                env={
                    "VOICE_DEMO_MOSHI_PYTHON": str(py),
                    "VOICE_DEMO_MOSHI_SNAPSHOT": str(snap),
                    "HF_HUB_OFFLINE": "1",
                },
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("snapshot file missing", proc.stderr.lower())
            self.assertNotIn("unexpected-download", proc.stderr)

    def test_run_modular_fails_without_caches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            py = tmp_path / "python"
            py.write_text("#!/bin/bash\necho should-not-run >&2\nexit 99\n", encoding="utf-8")
            py.chmod(py.stat().st_mode | stat.S_IEXEC)
            upstream = tmp_path / "hf"
            upstream.mkdir()
            missing_hf = tmp_path / "missing-hf"
            proc = run_bash(
                f'bash "{SCRIPTS}/run_modular.sh"',
                env={
                    "VOICE_DEMO_BACKEND_PYTHON": str(py),
                    "HF_S2S_REPO": str(upstream),
                    "VOICE_DEMO_HF_HOME": str(missing_hf),
                    "HF_HOME": str(missing_hf),
                },
            )
            self.assertEqual(proc.returncode, 2)
            self.assertIn("prepare_models", proc.stderr)
            self.assertNotIn("should-not-run", proc.stderr)

    def test_launch_nemotron_slot_uses_run_script_not_sbatch(self) -> None:
        text = (SCRIPTS / "launch_nemotron_slot.sh").read_text(encoding="utf-8")
        self.assertIn("run_nemotron.sh", text)
        self.assertNotIn("nemotron_server.sbatch", text)


class DownloadNgcSafetyTests(unittest.TestCase):
    def test_rejects_path_traversal(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "download_ngc", SCRIPTS / "download_ngc.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "models"
            target.mkdir()
            with self.assertRaises(ValueError):
                module.safe_relative_path("../escape.bin", target)
            with self.assertRaises(ValueError):
                module.safe_relative_path("/etc/passwd", target)
            ok = module.safe_relative_path("weights/model.bin", target)
            self.assertTrue(str(ok).startswith(str(target.resolve())))


class ScriptHygieneTests(unittest.TestCase):
    PERMITTED_SHELL = [
        "scripts/setup.sh",
        "scripts/setup_upstreams.sh",
        "scripts/setup_modular.sh",
        "scripts/setup_moshi.sh",
        "scripts/common.sh",
        "scripts/run_modular.sh",
        "scripts/run_moshi.sh",
        "scripts/run_demo.sh",
        "scripts/run_mock.sh",
        "scripts/launch_moshi_slot.sh",
        "scripts/launch_nemotron_slot.sh",
        "scripts/prepare_nemotron.sh",
        "scripts/run_nemotron.sh",
        "scripts/submit_slurm.sh",
        "scripts/setup_browser.sh",
        "scripts/run_browser_tests.sh",
        "scripts/prepare_test_audio.sh",
        "deploy/slurm/demo_ui.sbatch",
        "deploy/slurm/modular_server.sbatch",
        "deploy/slurm/end_to_end_server.sbatch",
        "deploy/slurm/nemotron_server.sbatch",
    ]

    def test_no_personal_paths_in_permitted_shell(self) -> None:
        pattern = re.compile(r"/home/[^/\s\"']+|/beegfs/work_fast/[^/\s\"']+/")
        for rel in self.PERMITTED_SHELL:
            text = (ROOT / rel).read_text(encoding="utf-8")
            match = pattern.search(text)
            self.assertIsNone(match, f"{rel} contains personal path: {match.group(0) if match else ''}")

    def test_submit_ui_replaced_by_submit_slurm(self) -> None:
        self.assertTrue((SCRIPTS / "submit_slurm.sh").is_file())
        self.assertFalse((SCRIPTS / "submit_ui.sh").exists())

    def test_slurm_templates_require_operator_gres_hint(self) -> None:
        for name in ("modular_server.sbatch", "end_to_end_server.sbatch", "nemotron_server.sbatch"):
            text = (ROOT / "deploy" / "slurm" / name).read_text(encoding="utf-8")
            self.assertIn("SLURM_JOB_GPUS", text)
            self.assertIn("CUDA_VISIBLE_DEVICES", text)
            self.assertNotIn("#SBATCH --partition=", text)
            self.assertNotIn("#SBATCH --qos=", text)
            self.assertNotIn("#SBATCH --gres=", text)
            self.assertNotIn("#SBATCH --chdir=", text)


if __name__ == "__main__":
    unittest.main()
