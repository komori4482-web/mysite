import os

from django.core.exceptions import ValidationError
from PIL import Image

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOC_EXTS = {".pdf", ".txt", ".md", ".zip", ".docx", ".xlsx", ".pptx"}
ALLOWED_EXTS = IMAGE_EXTS | DOC_EXTS

MAX_FILE_SIZE = 10 * 1024 * 1024  # 파일당 10MB
MAX_FILES_PER_POST = 5            # 글당 최대 5개


def get_ext(name):
    return os.path.splitext(name)[1].lower()


def is_image_name(name):
    return get_ext(name) in IMAGE_EXTS


def validate_attachment(f):
    """확장자(화이트리스트) · 크기 · 이미지 실제 내용을 검사한다.

    브라우저가 보내는 content_type 은 조작할 수 있어서 믿지 않는다.
    html/svg/js/exe 등은 허용 목록에 없으므로 모두 거절된다.
    """
    ext = get_ext(f.name)

    if ext not in ALLOWED_EXTS:
        raise ValidationError(
            f"'{f.name}': 올릴 수 없는 파일 형식입니다. "
            f"(허용: {', '.join(sorted(e.lstrip('.') for e in ALLOWED_EXTS))})"
        )

    if f.size > MAX_FILE_SIZE:
        raise ValidationError(
            f"'{f.name}': 파일이 너무 큽니다. (파일당 최대 {MAX_FILE_SIZE // 1024 // 1024}MB)"
        )

    if ext in IMAGE_EXTS:
        try:
            f.seek(0)
            Image.open(f).verify()
        except Exception:
            raise ValidationError(f"'{f.name}': 올바른 이미지 파일이 아니에요.")
        finally:
            f.seek(0)