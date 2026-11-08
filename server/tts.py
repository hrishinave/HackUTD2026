"""ElevenLabs voice for questions: pre-voiced bank clips and live renders.

Keys are read at call time. Every failure returns None so the page falls back to
the browser voice; nothing here may raise into the interview loop.
"""
import logging
import os

import httpx

log = logging.getLogger("pact.tts")

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
TIMEOUT_S = 3.0


def render(text: str) -> bytes | None:
    key = os.environ.get("ELEVEN_API_KEY")
    voice = os.environ.get("ELEVEN_VOICE_ID")
    if not key or not voice or not text.strip():
        return None
    try:
        r = httpx.post(
            URL.format(voice=voice),
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": os.environ.get("ELEVEN_MODEL", "eleven_flash_v2_5")},
            timeout=TIMEOUT_S,
        )
    except Exception as e:
        log.warning("tts failed (%s: %s)", type(e).__name__, e)
        return None
    if r.status_code != 200 or not r.content:
        log.warning("tts http %s", r.status_code)
        return None
    return r.content


def prevoice_bank(bank: dict, out_dir: str = "data/clips") -> int:
    """Write {out_dir}/{bank_id}.mp3 as "cue text" for each entry; skips existing files."""
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for bank_id in sorted(bank):
        path = os.path.join(out_dir, f"{bank_id}.mp3")
        if os.path.exists(path):
            continue
        q = bank[bank_id]
        audio = render(f"{q['cue']} {q['text']}")
        if audio is None:
            log.warning("no clip for %s", bank_id)
            continue
        with open(path, "wb") as f:
            f.write(audio)
        written += 1
    return written
