import asyncio
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.config import get_settings


async def save_upload(file: UploadFile, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    try:
        with target.open("wb") as output:
            while data := await file.read(64 * 1024):
                size += len(data)
                if size > get_settings().MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "File exceeds upload size limit")
                await asyncio.to_thread(output.write, data)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return size


def managed_path(raw: str | Path) -> Path:
    root = get_settings().UPLOAD_DIR.resolve()
    path = Path(raw)
    if not path.is_absolute():
        # Legacy paths were stored relative to the server working directory.
        path = root.parent / path
    path = path.resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError("Path is outside document storage")
    return path
