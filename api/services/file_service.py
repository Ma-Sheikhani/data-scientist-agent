import os
import uuid
from pathlib import Path

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))


def save_upload_file(file_content: bytes, original_filename: str) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(original_filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = UPLOAD_DIR / unique_name
    with open(file_path, "wb") as f:
        f.write(file_content)
    return str(unique_name)


def delete_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        os.remove(file_path)
