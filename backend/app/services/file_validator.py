from app.core.config import FILE_SIGNATURES


def validate_file_signature(content: bytes, extension: str) -> bool:
    check_range = content[:100] if len(content) > 100 else content
    for sig, exts in FILE_SIGNATURES.items():
        if sig in check_range:
            ext_name = extension.lstrip(".")
            return ext_name in exts
    return False


async def validate_file_type(content: bytes, extension: str) -> tuple[bool, str]:
    if not validate_file_signature(content, extension):
        return False, "文件内容与扩展名不匹配"
    return True, ""
