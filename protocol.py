"""
protocol.py — единый формат сообщений Starch.
"""

import json
from datetime import datetime

MSG = "msg"
SYS = "sys"
ONLINE = "online"
TYPING = "typing"
READ = "read"
EDIT = "edit"
DELETE = "delete"
REACTION = "reaction"
PING = "ping"
HISTORY = "history"
AUTH_OK = "auth_ok"
AUTH_ERR = "auth_err"
FILE = "file"
SEARCH = "search"


def pack(тип: str, **поля) -> str:
    данные = {"тип": тип, "время": datetime.now().strftime("%H:%M")}
    данные.update(поля)
    return json.dumps(данные, ensure_ascii=False)


def unpack(строка: str) -> dict:
    try:
        return json.loads(строка)
    except (json.JSONDecodeError, AttributeError):
        return {"тип": SYS, "текст": f"[битое сообщение] {строка[:50]}"}