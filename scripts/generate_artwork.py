#!/usr/bin/env python3
"""Generate original project SVG artwork and static capability badges."""
from pathlib import Path
from html import escape
import base64

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets/readme'


def svg(width, height, content, title):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}"><title>{escape(title)}</title>{content}</svg>\n'


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    header = '<defs><linearGradient id="panel" x2="1" y2="1"><stop stop-color="#172932"/><stop offset="1" stop-color="#101820"/></linearGradient><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10" fill="none" stroke="#aabac1" stroke-width="1.8"/></marker></defs>'
    content = header + '<rect width="1280" height="380" rx="24" fill="url(#panel)"/><rect x=".5" y=".5" width="1279" height="379" rx="24" fill="none" stroke="#30424c"/>'
    content += '<g font-family="Arial,Helvetica,sans-serif"><text x="56" y="53" fill="#83dfcd" font-size="15" letter-spacing="3">ONE SHARED INTERFACE</text><text x="56" y="94" fill="#f0f5f5" font-size="30" font-weight="700">Two ways to build a spoken conversation.</text>'
    content += '<text x="56" y="151" fill="#ffd0a0" font-size="16" font-weight="700" letter-spacing="2">MODULAR</text><text x="744" y="151" fill="#83dfcd" font-size="16" font-weight="700" letter-spacing="2">FULL-DUPLEX</text>'
    for i,(label,sub) in enumerate([('VAD','Detect speech'),('STT','Recognize'),('LLM','Respond'),('TTS','Speak')]):
        x = 56 + i*154
        content += f'<rect x="{x}" y="173" width="128" height="85" rx="13" fill="#202c30" stroke="#6c6655"/><text x="{x+18}" y="209" fill="#ffd0a0" font-size="23" font-weight="700">{label}</text><text x="{x+18}" y="236" fill="#c1cdd1" font-size="14">{sub}</text>'
        if i<3:content += f'<path d="M{x+132} 215h17" stroke="#aabac1" stroke-width="2" marker-end="url(#arrow)"/>'
    content += '<rect x="744" y="173" width="480" height="85" rx="13" fill="#193538" stroke="#4f9b8e"/><text x="766" y="209" fill="#83dfcd" font-size="23" font-weight="700">Moshi + Mimi</text><text x="766" y="236" fill="#c1cdd1" font-size="14">Speech in / speech out · continuous stream</text>'
    content += '<path d="M1110 206q14-26 28 0t28 0t28 0M1110 224q14 22 28 0t28 0t28 0" fill="none" stroke="#83dfcd" stroke-width="2.5" stroke-linecap="round"/>'
    content += '<path d="M56 291h1168" stroke="#30424c"/><text x="56" y="332" fill="#c1cdd1" font-size="19">Streaming audio</text><circle cx="245" cy="326" r="3" fill="#83dfcd"/><text x="269" y="332" fill="#c1cdd1" font-size="19">Warm backend switching</text><circle cx="558" cy="326" r="3" fill="#83dfcd"/><text x="582" y="332" fill="#c1cdd1" font-size="19">Capability-aware measurements</text></g>'
    (ASSETS/'hero.svg').write_text(svg(1280,380,content,'Modular and full-duplex speech architectures in one interface'))
    for name,left,right,color,width in [('license','CODE','Apache-2.0','#83dfcd',190),('architectures','PATHS','Modular + Moshi','#ffd0a0',240),('preview-mode','PREVIEW','CPU only','#b8d9fa',190)]:
        body=f'<rect width="{width}" height="28" rx="5" fill="#17232c"/><rect x=".5" y=".5" width="{width-1}" height="27" rx="5" fill="none" stroke="#30424c"/><g font-family="Arial,Helvetica,sans-serif" font-size="11" font-weight="700"><text x="12" y="18" fill="#aabac1">{left}</text><text x="{72 if name != "preview-mode" else 78}" y="18" fill="{color}">{right}</text></g>'
        (ASSETS/(name+'.svg')).write_text(svg(width,28,body,left+': '+right))
    social = '<rect width="1280" height="640" fill="#101820"/><circle cx="1130" cy="115" r="230" fill="#193538"/><g font-family="Arial,Helvetica,sans-serif"><text x="72" y="92" fill="#83dfcd" font-size="18" letter-spacing="3">SPEECH AI · ONE SHARED INTERFACE</text><text x="72" y="230" fill="#f0f5f5" font-size="76" font-weight="700">Real-Time</text><text x="72" y="324" fill="#f0f5f5" font-size="76" font-weight="700">Speech Dialogue</text><text x="76" y="398" fill="#b6c6cd" font-size="26">Compare modular and full-duplex voice AI.</text><text x="76" y="525" fill="#ffd0a0" font-size="25">VAD → STT → LLM → TTS</text><text x="76" y="575" fill="#83dfcd" font-size="25">Moshi + Mimi</text></g><path d="M1030 220q24-62 48 0t48 0t48 0M1030 290q24 62 48 0t48 0t48 0" fill="none" stroke="#83dfcd" stroke-width="6" stroke-linecap="round"/>'
    # Embed supplied originals so the exported cover has no external asset fetches.
    seal = base64.b64encode((ROOT/'frontend/branding/logo_tubs.jfif').read_bytes()).decode()
    ifn = base64.b64encode((ROOT/'frontend/branding/logo_IFN.svg').read_bytes()).decode()
    social += f'<rect x="910" y="471" width="300" height="133" rx="12" fill="#fff"/><image href="data:image/jpeg;base64,{seal}" x="924" y="489" width="100" height="100" preserveAspectRatio="xMidYMid meet"/><image href="data:image/svg+xml;base64,{ifn}" x="1040" y="491" width="152" height="96" preserveAspectRatio="xMidYMid meet"/>'
    (ASSETS/'social-preview.svg').write_text(svg(1280,640,social,'Real-Time Speech Dialogue project preview'))
    print('Generated project artwork and cover with supplied institutional marks; separate rights apply.')


if __name__ == '__main__':
    main()
