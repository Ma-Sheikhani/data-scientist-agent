"""File upload and cleanup service."""
import os
import uuid
from pathlib import Path


def _get_upload_dir() -> Path:
    """Return the upload directory, respecting the UPLOAD_DIR env variable."""
    return Path(os.getenv("UPLOAD_DIR", "/app/uploads"))


def save_upload_file(file_content: bytes, original_filename: str) -> str:
    upload_dir = _get_upload_dir()
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / unique_name
    with open(file_path, "wb") as f:
        f.write(file_content)
    return unique_name


def delete_file(filename: str):
    upload_dir = _get_upload_dir()
    file_path = upload_dir / filename
    if file_path.exists():
        os.remove(file_path)
