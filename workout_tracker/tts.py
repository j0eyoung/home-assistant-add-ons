"""Natural-sounding voices for the meditation sessions, made on the add-on with Piper (free, offline, neural).

Each voice is a ~60 MB model, downloaded the first time it is chosen into /data/voices (not baked into the
image, so the Green's small disk only holds the voices you actually use). Finished audio is cached in
/data/tts-cache, so a session you replay is instant. Models: huggingface.co/rhasspy/piper-voices (MIT)."""
import hashlib
import json
import os
import re
import threading
import urllib.request
import wave

VOICE_DIR = os.getenv("VOICE_DIR", "/data/voices")
AUDIO_DIR = os.getenv("TTS_CACHE_DIR", "/data/tts-cache")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/"

# id -> (label, description, path of the model on Hugging Face without extension)
VOICES = {
    "lessac": ("Lessac", "Warm, clear American", "en/en_US/lessac/medium/en_US-lessac-medium"),
    "amy": ("Amy", "Soft American", "en/en_US/amy/medium/en_US-amy-medium"),
    "kristin": ("Kristin", "Gentle American", "en/en_US/kristin/medium/en_US-kristin-medium"),
    "ljspeech": ("Linda", "Calm, even American", "en/en_US/ljspeech/medium/en_US-ljspeech-medium"),
    "hfc_female": ("Harper", "Bright American", "en/en_US/hfc_female/medium/en_US-hfc_female-medium"),
    "alba": ("Alba", "Scottish", "en/en_GB/alba/medium/en_GB-alba-medium"),
    "cori": ("Cori", "British", "en/en_GB/cori/medium/en_GB-cori-medium"),
    "jenny": ("Jenny", "Irish-English", "en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium"),
}
DEFAULT_VOICE = "lessac"
PREVIEW_TEXT = ("Settle into a comfortable position. Let your shoulders drop... and let your jaw soften. "
                "Breathe in slowly through your nose, and out, a little longer, through soft lips.")

_voices = {}
_jobs = {}
_lock = threading.Lock()
_KEY_RE = re.compile(r"^[0-9a-f]{16}$")


def voice_ready(voice_id):
    path = VOICES[voice_id][2]
    return os.path.exists(os.path.join(VOICE_DIR, os.path.basename(path) + ".onnx"))


def catalog():
    return [{"id": k, "label": v[0], "blurb": v[1], "ready": voice_ready(k)} for k, v in VOICES.items()]


def _download(url, dest):
    tmp = dest + ".tmp"
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)


def _load(voice_id):
    with _lock:
        if voice_id in _voices:
            return _voices[voice_id]
    from piper import PiperVoice
    path = VOICES[voice_id][2]
    base = os.path.join(VOICE_DIR, os.path.basename(path))
    os.makedirs(VOICE_DIR, exist_ok=True)
    for ext in (".onnx.json", ".onnx"):  # the small config first, so a broken download fails fast
        if not os.path.exists(base + ext):
            _download(HF + path + ext, base + ext)
    voice = PiperVoice.load(base + ".onnx")
    with _lock:
        _voices[voice_id] = voice
    return voice


def _make(job, voice_id, text):
    try:
        from piper import SynthesisConfig
        job["status"] = "loading"
        voice = _load(voice_id)
        cfg = SynthesisConfig(length_scale=1.2, noise_scale=0.6, noise_w_scale=0.7)  # slower, calmer
        paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()] or [text]
        sr = voice.config.sample_rate
        os.makedirs(AUDIO_DIR, exist_ok=True)
        tmp = job["path"] + ".tmp"
        job["status"] = "speaking"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            for i, para in enumerate(paragraphs):
                for chunk in voice.synthesize(para, syn_config=cfg):
                    w.writeframes(chunk.audio_int16_bytes)
                w.writeframes(b"\x00\x00" * int(sr * 2.5))  # a breath between paragraphs
                job["progress"] = round((i + 1) / len(paragraphs), 2)
        os.replace(tmp, job["path"])
        job["status"] = "ready"
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"{type(e).__name__}: {str(e)[:160]}"


def start(voice_id, text):
    """Start (or find) the audio for this voice and text. Returns the job."""
    if voice_id not in VOICES:
        voice_id = DEFAULT_VOICE
    key = hashlib.sha1(f"{voice_id}\n{text}".encode()).hexdigest()[:16]
    path = os.path.join(AUDIO_DIR, f"{key}.wav")
    with _lock:
        job = _jobs.get(key)
        if job and job["status"] in ("queued", "loading", "speaking"):
            return job
        if os.path.exists(path):
            job = _jobs[key] = {"key": key, "status": "ready", "progress": 1, "path": path}
            return job
        job = _jobs[key] = {"key": key, "status": "queued", "progress": 0, "path": path}
    threading.Thread(target=_make, args=(job, voice_id, text), daemon=True).start()
    return job


def _make_session(job, voice_id, segments):
    """A guided session as one audio file: each segment is spoken, then followed by `hold` seconds of quiet time to
    do the movement. The start and end of every segment is saved so the page can show the matching picture."""
    try:
        from piper import SynthesisConfig
        job["status"] = "loading"
        voice = _load(voice_id)
        cfg = SynthesisConfig(length_scale=1.2, noise_scale=0.6, noise_w_scale=0.7)
        sr = voice.config.sample_rate
        os.makedirs(AUDIO_DIR, exist_ok=True)
        tmp = job["path"] + ".tmp"
        timeline, frames = [], 0
        job["status"] = "speaking"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            for i, seg in enumerate(segments):
                start = frames / sr
                for chunk in voice.synthesize(seg["text"], syn_config=cfg):
                    w.writeframes(chunk.audio_int16_bytes)
                    frames += len(chunk.audio_int16_bytes) // 2
                quiet = int(sr * (seg.get("hold", 0) + 1.5))
                w.writeframes(b"\x00\x00" * quiet)
                frames += quiet
                timeline.append({"index": i, "start": round(start, 2), "end": round(frames / sr, 2)})
                job["progress"] = round((i + 1) / len(segments), 2)
        os.replace(tmp, job["path"])
        with open(job["path"][:-4] + ".json", "w", encoding="utf-8") as f:
            json.dump(timeline, f)
        job["status"] = "ready"
    except Exception as e:
        job["status"] = "error"
        job["error"] = f"{type(e).__name__}: {str(e)[:160]}"


def start_session(voice_id, segments):
    """Start (or find) a guided session's audio. Same job and status calls as start()."""
    if voice_id not in VOICES:
        voice_id = DEFAULT_VOICE
    key = hashlib.sha1(f"session\n{voice_id}\n{json.dumps(segments, sort_keys=True)}".encode()).hexdigest()[:16]
    path = os.path.join(AUDIO_DIR, f"{key}.wav")
    with _lock:
        job = _jobs.get(key)
        if job and job["status"] in ("queued", "loading", "speaking"):
            return job
        if os.path.exists(path) and os.path.exists(path[:-4] + ".json"):
            job = _jobs[key] = {"key": key, "status": "ready", "progress": 1, "path": path}
            return job
        job = _jobs[key] = {"key": key, "status": "queued", "progress": 0, "path": path}
    threading.Thread(target=_make_session, args=(job, voice_id, segments), daemon=True).start()
    return job


def timeline(key):
    path = os.path.join(AUDIO_DIR, f"{key}.json")
    if not _KEY_RE.match(key) or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def status(key):
    job = _jobs.get(key)
    if job:
        return job
    path = os.path.join(AUDIO_DIR, f"{key}.wav")
    if _KEY_RE.match(key) and os.path.exists(path):
        return {"key": key, "status": "ready", "progress": 1, "path": path}
    return None


def public(job):
    return {"key": job["key"], "status": job["status"], "progress": job.get("progress", 0), "error": job.get("error")}
