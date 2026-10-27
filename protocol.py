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
SEARCH = "search"

# Новые типы для медиа
IMAGE = "image"
VOICE = "voice"
CALL_OFFER = "call_offer"
CALL_ANSWER = "call_answer"
CALL_ICE = "call_ice"
CALL_END = "call_end"

def pack(тип: str, **поля) -> str:
    данные = {"тип": тип, "время": datetime.now().strftime("%H:%M")}
    данные.update(поля)
    return json.dumps(данные, ensure_ascii=False)

def unpack(строка: str) -> dict:
    try:
        return json.loads(строка)
    except (json.JSONDecodeError, AttributeError):
        return {"тип": SYS, "текст": f"[битое сообщение] {строка[:50]}"}