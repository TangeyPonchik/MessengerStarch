import sys
import io

if sys.stdout is not None and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr is not None and sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import asyncio
import base64
import os
import uuid
from typing import Dict
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel

import database as db
import ai as lazur
from auth import create_token, verify_token, hash_password
from protocol import (
    pack, unpack, MSG, SYS, ONLINE, TYPING, READ, EDIT, DELETE,
    REACTION, PING, HISTORY, AUTH_OK, SEARCH, IMAGE, VOICE,
    CALL_OFFER, CALL_ANSWER, CALL_ICE, CALL_END
)

app = FastAPI(title="Starch Server")

class Менеджер:
    def __init__(self):
        self.по_юзеру: Dict[int, WebSocket] = {}

    async def подключить(self, user_id: int, ws: WebSocket):
        self.по_юзеру[user_id] = ws

    def отключить(self, user_id: int):
        self.по_юзеру.pop(user_id, None)

    async def отправить(self, user_id: int, текст: str) -> bool:
        ws = self.по_юзеру.get(user_id)
        if not ws: return False
        try:
            await ws.send_text(текст)
            return True
        except Exception:
            self.отключить(user_id)
            return False

    async def разослать(self, текст: str):
        for uid in list(self.по_юзеру.keys()):
            await self.отправить(uid, текст)

    def онлайн(self) -> list:
        return list(self.по_юзеру.keys())

менеджер = Менеджер()

class AuthRequest(BaseModel):
    username: str
    password: str

@app.get("/")
async def корень():
    return {"сервис": "Starch", "онлайн": len(менеджер.онлайн())}

@app.post("/register")
async def регистрация(req: AuthRequest):
    username = req.username.strip()
    if len(username) < 2 or len(username) > 20:
        raise HTTPException(400, "Ник: 2–20 символов")
    if len(req.password) < 4:
        raise HTTPException(400, "Пароль: минимум 4 символа")
    uid, err = db.register_user(username, hash_password(req.password))
    if err: raise HTTPException(400, err)
    token = create_token(uid)
    return {"token": token, "user_id": uid, "username": username}

@app.post("/login")
async def логин(req: AuthRequest):
    user = db.get_user_by_username(req.username.strip())
    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(401, "Неверный логин или пароль")
    token = create_token(user["id"])
    return {"token": token, "user_id": user["id"], "username": user["username"]}

@app.post("/upload")
async def загрузка_файла(file: UploadFile = File(...)):
    расширение = os.path.splitext(file.filename)[1]
    имя = f"{uuid.uuid4().hex}{расширение}"
    путь = os.path.join(db.MEDIA_DIR, имя)
    with open(путь, "wb") as f:
        f.write(await file.read())
    return {"url": f"/media/{имя}", "type": "image" if расширение in [".jpg", ".png", ".jpeg", ".gif"] else "voice"}

@app.get("/media/{имя}")
async def получить_медиа(имя: str):
    путь = os.path.join(db.MEDIA_DIR, имя)
    if not os.path.exists(путь):
        raise HTTPException(404)
    return FileResponse(путь)

@app.websocket("/ws/{token}")
async def websocket_эндпоинт(ws: WebSocket, token: str):
    user_id = verify_token(token)
    if user_id is None: await ws.close(code=4001); return
    user = db.get_user_by_id(user_id)
    if not user: await ws.close(code=4001); return

    await ws.accept()
    старый = менеджер.по_юзеру.get(user_id)
    if старый and старый is not ws:
        try: await старый.close()
        except: pass
    await менеджер.подключить(user_id, ws)
    print(f"[Starch] {user['username']} подключён.")
    await ws.send_text(pack(AUTH_OK, user_id=user_id, username=user["username"]))
    await менеджер.разослать(pack(ONLINE, users=менеджер.онлайн()))

    async def heartbeat():
        while True:
            await asyncio.sleep(20)
            try: await ws.send_text(pack(PING))
            except: return
    ping_task = asyncio.create_task(heartbeat())

    try:
        while True:
            сырое = await ws.receive_text()
            данные = unpack(сырое)
            тип = данные.get("тип")

            if тип == PING: continue

            if тип == TYPING:
                peer = данные.get("to")
                if peer: await менеджер.отправить(peer, pack(TYPING, from_id=user_id, from_name=user["username"]))
                continue

            if тип == SEARCH:
                запрос = данные.get("запрос", "").strip()
                peer = данные.get("peer")
                if not запрос: continue
                результаты = db.search_messages(user_id, peer, запрос)
                await менеджер.отправить(user_id, pack(SEARCH, peer=peer, запрос=запрос, результаты=результаты))
                continue

            # Звонки (WebRTC signaling)
            if тип in [CALL_OFFER, CALL_ANSWER, CALL_ICE, CALL_END]:
                peer = данные.get("to")
                if peer:
                    данные["from"] = user_id
                    await менеджер.отправить(peer, json.dumps(данные))
                continue

            if тип == MSG:
                текст = (данные.get("текст") or "").strip()
                to_user = данные.get("to")
                reply_to = данные.get("reply_to")
                media_url = данные.get("media_url")
                media_type = данные.get("media_type")

                saved = db.save_message(user_id, to_user, текст, media_url, media_type, reply_to)
                исходящее = pack(
                    MSG, id=saved["id"], from_id=user_id, from_name=user["username"],
                    to_user=to_user, текст=текст, media_url=media_url, media_type=media_type,
                    reply_to=reply_to, edited=0,
                )
                if to_user is None: await менеджер.разослать(исходящее)
                else:
                    await менеджер.отправить(to_user, исходящее)
                    await менеджер.отправить(user_id, исходящее)

                # Lazur-lite
                low = текст.lower().lstrip()
                в_личке_с_lazur = (to_user == lazur.LAZUR_USER_ID)
                вызов_бота = low.startswith("@lazur-lite") or low.startswith("@lazurlite")
                if (вызов_бота or в_личке_с_lazur) and user_id != lazur.LAZUR_USER_ID:
                    ответ = lazur.ответить(текст, user["username"], user_id, user["username"])
                    ответ_кому = user_id if в_личке_с_lazur else to_user
                    saved_ответ = db.save_message(lazur.LAZUR_USER_ID, ответ_кому, ответ)
                    исходящее_ответ = pack(MSG, id=saved_ответ["id"], from_id=lazur.LAZUR_USER_ID,
                        from_name=lazur.LAZUR_NAME, to_user=ответ_кому, текст=ответ, reply_to=None, edited=0)
                    if ответ_кому is None: await менеджер.разослать(исходящее_ответ)
                    else: await менеджер.отправить(ответ_кому, исходящее_ответ)
                continue

            if тип == HISTORY:
                peer = данные.get("peer")
                история = db.get_history(user_id, peer)
                await менеджер.отправить(user_id, pack(HISTORY, peer=peer, messages=история))
                continue

            if тип == EDIT:
                mid = данные.get("id")
                новый = (данные.get("текст") or "").strip()
                if mid and новый and db.edit_message(mid, user_id, новый):
                    await менеджер.разослать(pack(EDIT, id=mid, текст=новый))
                continue

            if тип == DELETE:
                mid = данные.get("id")
                if mid and db.delete_message(mid, user_id):
                    await менеджер.разослать(pack(DELETE, id=mid))
                continue

            if тип == REACTION:
                mid = данные.get("id")
                emoji = данные.get("emoji")
                if mid and emoji:
                    db.toggle_reaction(mid, user_id, emoji)
                    реакции = db.get_reactions(mid)
                    await менеджер.разослать(pack(REACTION, id=mid, реакции=реакции))
                continue

    except WebSocketDisconnect:
        менеджер.отключить(user_id)
        await менеджер.разослать(pack(ONLINE, users=менеджер.онлайн()))
    except Exception as e:
        print(f"[Starch] ошибка: {e}")
        менеджер.отключить(user_id)
    finally:
        ping_task.cancel()

if __name__ == "__main__":
    db.init_db()
    uvicorn.run(app, host="127.0.0.1", port=8000, ws_ping_interval=20, ws_ping_timeout=60)