from datetime import datetime, timezone

def fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso

def short_hwid(hwid: str | None) -> str:
    if not hwid:
        return "не привязан"
    return hwid

def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
