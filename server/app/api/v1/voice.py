import uuid

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.config import get_settings
from app.security import require_owner
from app.storage import save_upload

router = APIRouter(prefix="/voice", tags=["Voice Input"])


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...), owner: str = Depends(require_owner)):
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise HTTPException(503, "Voice transcription is not configured")
    if file.content_type not in {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}:
        raise HTTPException(415, "Unsupported audio type")
    mime_type = file.content_type
    extensions = {
        "audio/webm": ".webm",
        "audio/ogg": ".ogg",
        "audio/mp4": ".mp4",
        "audio/wav": ".wav",
        "audio/mpeg": ".mp3",
    }
    path = settings.UPLOAD_DIR / "voice" / str(uuid.uuid4())
    try:
        await save_upload(file, path)
        async with httpx.AsyncClient(timeout=30.0) as client:
            with path.open("rb") as audio:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                    files={"file": (f"recording{extensions[mime_type]}", audio, mime_type)},
                    data={"model": "whisper-large-v3", "language": "en"},
                )
            response.raise_for_status()
            text = response.json().get("text", "").strip()
            if not text:
                raise ValueError("Empty transcription")
            return {"text": text, "provider": "groq-whisper"}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Transcription failed; no text was generated") from exc
    finally:
        path.unlink(missing_ok=True)
