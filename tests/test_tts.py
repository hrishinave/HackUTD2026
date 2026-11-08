import httpx

from server import tts


class _Resp:
    def __init__(self, status, content=b""):
        self.status_code, self.content = status, content


def test_render_posts_to_elevenlabs_and_returns_bytes(monkeypatch):
    monkeypatch.setenv("ELEVEN_API_KEY", "k"); monkeypatch.setenv("ELEVEN_VOICE_ID", "v")
    seen = {}
    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json, timeout=timeout)
        return _Resp(200, b"ID3mp3")
    monkeypatch.setattr(tts.httpx, "post", fake_post)
    assert tts.render("Gap: Where does it go?") == b"ID3mp3"
    assert seen["url"].startswith("https://api.elevenlabs.io/v1/text-to-speech/v") and "mp3_44100_128" in seen["url"]
    assert seen["headers"]["xi-api-key"] == "k" and seen["json"]["text"] == "Gap: Where does it go?" and seen["timeout"] == 3.0


def test_render_returns_none_on_failure_or_missing_key(monkeypatch):
    monkeypatch.setenv("ELEVEN_API_KEY", "k"); monkeypatch.setenv("ELEVEN_VOICE_ID", "v")
    monkeypatch.setattr(tts.httpx, "post", lambda *a, **k: _Resp(401))
    assert tts.render("hi?") is None
    def boom(*a, **k): raise httpx.ReadTimeout("slow")
    monkeypatch.setattr(tts.httpx, "post", boom)
    assert tts.render("hi?") is None
    monkeypatch.delenv("ELEVEN_API_KEY")
    assert tts.render("hi?") is None


def test_prevoice_bank_writes_cue_and_text_and_skips_existing(tmp_path, monkeypatch):
    spoken = []
    monkeypatch.setattr(tts, "render", lambda text: spoken.append(text) or b"mp3")
    (tmp_path / "PQ-02.mp3").write_bytes(b"old")
    bank = {"PQ-01": {"cue": "Gap:", "text": "Where?"}, "PQ-02": {"cue": "Detail:", "text": "When?"}}
    assert tts.prevoice_bank(bank, out_dir=str(tmp_path)) == 1
    assert spoken == ["Gap: Where?"] and (tmp_path / "PQ-01.mp3").read_bytes() == b"mp3"
    assert (tmp_path / "PQ-02.mp3").read_bytes() == b"old"


def test_clips_are_served(tmp_path):
    import os
    from fastapi.testclient import TestClient
    from server.app import app
    path = "data/clips/PQ-TEST.mp3"
    with open(path, "wb") as f:
        f.write(b"ID3x")
    try:
        r = TestClient(app).get("/clips/PQ-TEST.mp3")
        assert r.status_code == 200 and r.content == b"ID3x"
    finally:
        os.remove(path)
