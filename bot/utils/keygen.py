import secrets
import string
import re
from datetime import datetime, timedelta, timezone

# Используется charset из настроек, но дефолт:
DEFAULT_CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_key(
    prefix: str = "KP",
    segments: int = 4,
    segment_len: int = 4,
    charset: str = DEFAULT_CHARSET,
) -> str:
    parts = []
    for _ in range(segments):
        seg = "".join(secrets.choice(charset) for _ in range(segment_len))
        parts.append(seg)
    if prefix:
        return f"{prefix}-{'-'.join(parts)}"
    return "-".join(parts)


def parse_key_format(fmt: str) -> tuple[str, int, int]:
    """
    Парсит формат вида KP-XXXX-XXXX-XXXX
    Возвращает (prefix, segments, segment_len)
    X = символ из charset
    """
    fmt = fmt.strip().upper()
    parts = fmt.split("-")
    prefix = ""
    segments = []
    for p in parts:
        if set(p) == {"X"}:
            segments.append(len(p))
        elif p and not prefix:
            prefix = p
        elif set(p) == {"X"}:
            segments.append(len(p))
    if not segments:
        return "KP", 4, 4
    # считаем что все сегменты одинаковой длины (берём первый)
    seg_len = segments[0]
    seg_count = len(segments)
    return prefix, seg_count, seg_len


def calc_expires(days: int) -> str | None:
    if days == 0:
        return None  # навсегда
    dt = datetime.now(timezone.utc) + timedelta(days=days)
    return dt.isoformat()
