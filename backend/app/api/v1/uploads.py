"""Upload endpoints.

Принимает изображение (multipart/form-data), сохраняет его
в директорию uploads/categories или uploads/products и возвращает
публичный URL вида /uploads/categories/<filename>.
"""
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_admin_user
from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.user import User

router = APIRouter(tags=["Uploads"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

Kind = Literal["categories", "products"]


def _safe_filename(original: str) -> str:
    """Возвращает безопасное имя файла с уникальным суффиксом."""
    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise BadRequestError(
            "Недопустимый формат файла. Разрешены: "
            + ", ".join(sorted(ALLOWED_EXTENSIONS))
        )
    stem = Path(original).stem
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", stem)
    stem = stem[:80] or "image"
    return f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"


@router.post("", response_model=dict)
async def upload_image(
    folder: Kind = Form(...),
    file: UploadFile = File(...),
    admin: User = Depends(get_admin_user),
):
    if folder not in ("categories", "products"):
        raise BadRequestError("Неизвестная папка для загрузки")

    target_dir: Path = (
        settings.categories_upload_dir
        if folder == "categories"
        else settings.products_upload_dir
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_filename(file.filename or "image")

    data = await file.read()
    if len(data) == 0:
        raise BadRequestError("Файл пустой")
    if len(data) > settings.max_upload_size_bytes:
        raise BadRequestError(
            f"Файл слишком большой. Максимум {settings.max_upload_size_mb} МБ"
        )

    target = target_dir / filename
    target.write_bytes(data)

    url = f"/uploads/{folder}/{filename}"
    return {"url": url}
