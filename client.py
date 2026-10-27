import customtkinter as ctk
import threading
import queue
import json
import os
import sys
import time
import requests
import websocket
from PIL import Image
import io

from protocol import *
from input import открыть_эмодзи, ЗаписьГолоса, создать_панель_ввода

SERVER_HTTP = "http://127.0.0.1:8000"
SERVER_WS = "ws://127.0.0.1:8000/ws"

if getattr(sys, 'frozen', False): BASE_DIR = os.path.dirname(sys.executable)
else: BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BASE_DIR, "starch_session.json")

LAZUR_ID = 999
LAZUR_NAME = "Lazur-lite"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG, SIDEBAR, ACTIVE_CHAT = "#17212b", "#0e1621", "#2b5278"
BUBBLE_OWN, BUBBLE_OTHER, BUBBLE_LAZUR = "#2b5278", "#182533", "#3a2a5a"
TEXT, MUTED, ACCENT, LAZUR_COLOR = "#ffffff", "#7d8e98", "#4dabf7", "#b794f6"

class StarchApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Starch")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(fg_color=BG)

        self.token = self.user_id = self.username = None
        self.ws = None
        self.ws_готов = False
        self.очередь = queue.Queue()
        self._последний_typing = 0
        self._переподключение_идёт = False

        self.текущий_peer = None
        self.контакты = {}
        self.чат_метки = {}
        self.пользователи_онлайн = set()
        
        self.call_active = False

        self._экран_логина()
        self._экран_чата()
        self._показать_логин()
        self.after(100, self._попробовать_восстановить)

    def _экран_логина(self):
        self.логин = ctk.CTkFrame(self, fg_color=BG)
        центр = ctk.CTkFrame(self.логин, fg_color="transparent")
        центр.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(центр, text="Starch", font=("Segoe UI", 56, "bold"), text_color=ACCENT).pack(pady=(0, 6))
        ctk.CTkLabel(центр, text="Безопасный чат на Python", font=("Segoe UI", 14), text_color=MUTED).pack(pady=(0, 30))
        self.ник_поле = ctk.CTkEntry(центр, placeholder_text="Логин", height=45, width=320, font=("Segoe UI", 16))
        self.ник_поле.pack(pady=6)
        self.пароль_поле = ctk.CTkEntry(центр, placeholder_text="Пароль", height=45, width=320, font=("Segoe UI", 16), show="*")
        self.пароль_поле.pack(pady=6)
        self.пароль_поле.bind("<Return>", lambda e: self._войти())
        рамка = ctk.CTkFrame(центр, fg_color="transparent")
        рамка.pack(pady=10)
        ctk.CTkButton(рамка, text="Войти", height=45, width=155, font=("Segoe UI", 16, "bold"), fg_color=ACCENT, command=self._войти).pack(side="left", padx=4)
        ctk.CTkButton(рамка, text="Регистрация", height=45, width=155, font=("Segoe UI", 16), fg_color="#2b5278", command=self._регистрация).pack(side="left", padx=4)
        self.статус_логина = ctk.CTkLabel(центр, text="", font=("Segoe UI", 12), text_color="#f44")
        self.статус_логина.pack(pady=10)

    def _экран_чата(self):
        self.чат = ctk.CTkFrame(self, fg_color=BG)
        self.sidebar = ctk.CTkFrame(self.чат, width=260, fg_color=SIDEBAR, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(self.sidebar, text="Starch", font=("Segoe UI", 22, "bold"), text_color=ACCENT).pack(pady=(20, 5), padx=15, anchor="w")
        self.я_лейбл = ctk.CTkLabel(self.sidebar, text="", font=("Segoe UI", 12), text_color=MUTED)
        self.я_лейбл.pack(padx=15, anchor="w", pady=(0, 15))
        ctk.CTkLabel(self.sidebar, text="ЧАТЫ", font=("Segoe UI", 10, "bold"), text_color=MUTED).pack(padx=15, pady=(5, 5), anchor="w")
        self.контакты_рамка = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.контакты_рамка.pack(fill="both", expand=True, padx=5, pady=5)

        self.main = ctk.CTkFrame(self.чат, fg_color=BG, corner_radius=0)
        self.main.pack(side="right", fill="both", expand=True)
        self.шапка = ctk.CTkFrame(self.main, height=60, fg_color=SIDEBAR, corner_radius=0)
        self.шапка.pack(fill="x")
        self.шапка.pack_propagate(False)
        self.шапка_название = ctk.CTkLabel(self.шапка, text="Общий чат", font=("Segoe UI", 18, "bold"), text_color=TEXT)
        self.шапка_название.pack(side="left", padx=20, pady=15)
        self.шапка_статус = ctk.CTkLabel(self.шапка, text="", font=("Segoe UI", 11), text_color=MUTED)
        self.шапка_статус.pack(side="left", padx=10)
        self.звонок_btn = ctk.CTkButton(self.шапка, text="📞", width=40, height=35, fg_color="#2b5278", command=self._начать_звонок)
        self.звонок_btn.pack(side="right", padx=10)

        self.история = ctk.CTkScrollableFrame(self.main, fg_color=BG)
        self.история.pack(fill="both", expand=True, padx=10, pady=10)
        self.печатает_лейбл = ctk.CTkLabel(self.main, text="", font=("Segoe UI", 11, "italic"), text_color=MUTED)
        self.печатает_лейбл.pack(padx=20, anchor="w")

        # ВЫЗОВ ПАНЕЛИ ВВОДА ИЗ input.py
        self.поле = создать_панель_ввода(self.main, self)

        self.reply_баннер = None
        self.reply_to = None

    def _сохранить_сессию(self):
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"token": self.token, "user_id": self.user_id, "username": self.username}, f, ensure_ascii=False)
        except: pass

    def _попробовать_восстановить(self):
        if not os.path.exists(SESSION_FILE): return
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                данные = json.load(f)
            self.token, self.user_id, self.username = данные["token"], данные["user_id"], данные["username"]
            threading.Thread(target=self._подключиться, daemon=True).start()
        except: pass

    def _показать_логин(self): self.чат.pack_forget(); self.логин.pack(fill="both", expand=True)
    def _показать_чат(self):
        self.логин.pack_forget(); self.чат.pack(fill="both", expand=True)
        self.поле.focus_set(); self.я_лейбл.configure(text=f"@{self.username}")
        self._обновить_контакты(); self.after(150, lambda: self._запросить_историю(None))

    def _войти(self): self._авторизация("/login")
    def _регистрация(self): self._авторизация("/register")

    def _авторизация(self, endpoint):
        логин = self.ник_поле.get().strip()
        пароль = self.пароль_поле.get().strip()
        if not логин or not пароль:
            self.статус_логина.configure(text="Заполни оба поля", text_color="#f44")
            return
        self.статус_логина.configure(text="...", text_color="#fa0")
        threading.Thread(target=self._http_auth, args=(endpoint, логин, пароль), daemon=True).start()

    def _http_auth(self, endpoint, логин, пароль):
        for попытка in range(3):
            try:
                r = requests.post(SERVER_HTTP + endpoint, json={"username": логин, "password": пароль}, timeout=5)
                if r.status_code != 200:
                    self.after(0, lambda: self.статус_логина.configure(text=r.json().get("detail", "Ошибка"), text_color="#f44"))
                    return
                данные = r.json()
                self.token, self.user_id, self.username = данные["token"], данные["user_id"], данные["username"]
                self._сохранить_сессию()
                threading.Thread(target=self._подключиться, daemon=True).start()
                return
            except requests.exceptions.ConnectionError:
                if попытка < 2: time.sleep(1.5)
                else: self.after(0, lambda: self.статус_логина.configure(text="Сервер не запущен", text_color="#f44"))
            except Exception as e:
                self.after(0, lambda: self.статус_логина.configure(text=f"Ошибка: {e}", text_color="#f44"))
                return

    def _подключиться(self):
        try:
            self.ws = websocket.create_connection(f"{SERVER_WS}/{self.token}")
            self.ws_готов = True
            threading.Thread(target=self._читатель, daemon=True).start()
            self.after(50, self._разобрать_очередь)
            self.after(0, self._показать_чат)
        except Exception as e:
            self.after(0, lambda: self.статус_логина.configure(text=f"WebSocket: {e}", text_color="#f44"))
            if self.token: self.after(3000, self._переподключиться)

    def _читатель(self):
        while self.ws_готов:
            try:
                msg = self.ws.recv()
                if not msg: break
                self.очередь.put(msg)
            except: break
        self.очередь.put(None)

    def _разобрать_очередь(self):
        try:
            while True:
                msg = self.очередь.get_nowait()
                if msg is None:
                    self.ws_готов = False
                    if self.token and not self._переподключение_идёт:
                        self._переподключение_идёт = True
                        self.after(3000, self._переподключиться)
                    return
                self._обработать(unpack(msg))
        except queue.Empty: pass
        if self.ws_готов: self.after(50, self._разобрать_очередь)

    def _переподключиться(self):
        self._переподключение_идёт = False
        if self.ws_готов or not self.token: return
        threading.Thread(target=self._подключиться_заново, daemon=True).start()

    def _подключиться_заново(self):
        try:
            self.ws = websocket.create_connection(f"{SERVER_WS}/{self.token}")
            self.ws_готов = True
            threading.Thread(target=self._читатель, daemon=True).start()
            self.after(50, self._разобрать_очередь)
            self.after(100, lambda: self._запросить_историю(self.текущий_peer))
        except:
            if not self._переподключение_идёт:
                self._переподключение_идёт = True
                self.after(5000, self._переподключиться)

    def _обработать(self, д):
        тип = д.get("тип")
        if тип == PING:
            try: self.ws.send(pack(PING))
            except: pass
            return
        if тип == AUTH_OK: return
        if тип == ONLINE:
            self.пользователи_онлайн = set(д.get("users", []))
            self._обновить_контакты()
        elif тип == HISTORY:
            peer = д.get("peer")
            if peer != self.текущий_peer: return
            for виджет in self.история.winfo_children(): виджет.destroy()
            self.чат_метки.clear()
            for m in д.get("messages", []): self._нарисовать_сообщение(m)
        elif тип == SEARCH:
            peer = д.get("peer")
            if peer != self.текущий_peer: return
            for виджет in self.история.winfo_children(): виджет.destroy()
            self.чат_метки.clear()
            for m in д.get("результаты", []): self._нарисовать_сообщение(m)
        elif тип == MSG:
            from_id = д.get("from_id")
            if from_id and from_id != self.user_id and from_id != LAZUR_ID:
                self.контакты[from_id] = д.get("from_name")
                self._обновить_контакты()
            to_user = д.get("to_user")
            свой = (from_id == self.user_id)
            if to_user is None:
                if self.текущий_peer is None: self._нарисовать_сообщение(д)
            elif self.текущий_peer == (from_id if not свой else to_user):
                self._нарисовать_сообщение(д)
        elif тип == TYPING:
            if д.get("from_id") == self.текущий_peer:
                self.печатает_лейбл.configure(text=f"{д.get('from_name')} печатает...")
                self.after(2000, lambda: self.печатает_лейбл.configure(text=""))
        elif тип == EDIT:
            mid = д.get("id")
            if mid in self.чат_метки:
                try: self.чат_метки[mid].configure(text=д.get("текст", ""))
                except: pass
        elif тип == DELETE:
            mid = д.get("id")
            if mid in self.чат_метки:
                try: self.чат_метки[mid].destroy()
                except: pass
                self.чат_метки.pop(mid, None)
        elif тип == CALL_OFFER:
            self._входящий_звонок(д)
        elif тип == CALL_ANSWER:
            self.call_active = True
            self._добавить_системное("[звонок] Собеседник ответил!")
        elif тип == CALL_END:
            self._завершить_звонок()

    def _обновить_контакты(self):
        for w in self.контакты_рамка.winfo_children(): w.destroy()
        self._кнопка_контакта(None, "Общий чат", online=True)
        self._кнопка_контакта(LAZUR_ID, f"🤖 {LAZUR_NAME}", online=True)
        for uid, name in sorted(self.контакты.items(), key=lambda x: x[1]):
            if uid == LAZUR_ID: continue
            self._кнопка_контакта(uid, name, online=uid in self.пользователи_онлайн)

    def _кнопка_контакта(self, peer, name, online):
        btn = ctk.CTkButton(self.контакты_рамка, text=("● " if online else "○ ") + name,
            anchor="w", fg_color=ACTIVE_CHAT if peer == self.текущий_peer else "transparent",
            hover_color="#1c2b3a", font=("Segoe UI", 14), height=40, corner_radius=8,
            text_color=TEXT if online else MUTED, command=lambda: self._выбрать_чат(peer, name))
        btn.pack(fill="x", pady=2, padx=4)

    def _выбрать_чат(self, peer, name):
        self.текущий_peer = peer
        self.шапка_название.configure(text=name)
        for w in self.история.winfo_children(): w.destroy()
        self.чат_метки.clear()
        self._обновить_контакты()
        self._запросить_историю(peer)

    def _запросить_историю(self, peer):
        if self.ws_готов:
            try: self.ws.send(pack(HISTORY, peer=peer))
            except: pass

    def _добавить_системное(self, текст):
        ctk.CTkLabel(self.история, text=текст, font=("Segoe UI", 11, "italic"), text_color=MUTED).pack(pady=4, padx=8)

    def _нарисовать_сообщение(self, m):
        свой = (m.get("from_id") == self.user_id)
        from_lazur = (m.get("from_id") == LAZUR_ID)
        автор = m.get("from_name", "?")
        текст = m.get("текст", "")
        время = m.get("время", "")
        edited = m.get("edited", 0)
        media_url = m.get("media_url")
        media_type = m.get("media_type")

        строка = ctk.CTkFrame(self.история, fg_color="transparent")
        строка.pack(fill="x", pady=3, padx=8)

        bg = BUBBLE_LAZUR if from_lazur else (BUBBLE_OWN if свой else BUBBLE_OTHER)
        bubble = ctk.CTkFrame(строка, fg_color=bg, corner_radius=12)
        bubble.pack(side="right" if свой else "left")

        if not свой:
            ctk.CTkLabel(bubble, text=автор, font=("Segoe UI", 11, "bold"), text_color=LAZUR_COLOR if from_lazur else ACCENT).pack(anchor="w", padx=10, pady=(6, 0))

        if media_url and media_type == "image":
            try:
                url = SERVER_HTTP + media_url
                res = requests.get(url, timeout=5)
                img = Image.open(io.BytesIO(res.content))
                img.thumbnail((300, 300))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                lbl = ctk.CTkLabel(bubble, image=ctk_img, text="")
                lbl.pack(padx=10, pady=5)
            except Exception as e:
                ctk.CTkLabel(bubble, text=f"[картинка: {e}]", text_color="#f44").pack(padx=10, pady=5)
        elif media_url and media_type == "voice":
            url = SERVER_HTTP + media_url
            ctk.CTkLabel(bubble, text=f"🎤 Голосовое\n{url}", text_color=ACCENT, font=("Segoe UI", 12)).pack(padx=10, pady=5)

        if текст:
            текст_метка = ctk.CTkLabel(bubble, text=текст, font=("Segoe UI", 14), text_color=TEXT, anchor="w", justify="left", wraplength=500)
            текст_метка.pack(anchor="w", padx=10, pady=(2, 2))
            self.чат_метки[m.get("id")] = текст_метка

        ctk.CTkLabel(bubble, text=(f"{время} · изм." if edited else время), font=("Segoe UI", 9), text_color=MUTED).pack(anchor="e", padx=10, pady=(0, 6))
        self._прокрутить_вниз()

    def _прокрутить_вниз(self):
        try: self.история._parent_canvas.yview_moveto(1.0)
        except: pass

    def _по_enter(self, event):
        if event.state & 0x0004 or event.state & 0x0008: return None
        self._отправить()
        return "break"

    def _печатаю(self, event=None):
        if not self.ws_готов or not self.текущий_peer: return
        сейчас = time.time()
        if сейчас - self._последний_typing < 2: return
        self._последний_typing = сейчас
        try: self.ws.send(pack(TYPING, to=self.текущий_peer))
        except: pass

    def _отправить(self):
        if not self.ws_готов: return
        текст = self.поле.get().strip()
        if not текст: return
        try:
            self.ws.send(pack(MSG, to=self.текущий_peer, текст=текст))
            self.поле.delete(0, "end")
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    def _выбрать_картинку(self):
        from tkinter import filedialog
        путь = filedialog.askopenfilename(filetypes=[("Картинки", "*.png *.jpg *.jpeg *.gif")])
        if not путь: return
        threading.Thread(target=self._загрузить_медиа, args=(путь, "image"), daemon=True).start()

    def _записать_голос(self):
        ЗаписьГолоса(self, lambda файл: threading.Thread(target=self._загрузить_медиа, args=(файл, "voice"), daemon=True).start())

    def _загрузить_медиа(self, путь, тип):
        try:
            with open(путь, "rb") as f:
                r = requests.post(f"{SERVER_HTTP}/upload", files={"file": f})
            if r.status_code == 200:
                url = r.json()["url"]
                self.ws.send(pack(MSG, to=self.текущий_peer, текст="", media_url=url, media_type=тип))
            else:
                self._добавить_системное(f"[ошибка загрузки] {r.status_code}")
        except Exception as e:
            self._добавить_системное(f"[ошибка] {e}")

    def _начать_звонок(self):
        if not self.текущий_peer or self.текущий_peer == LAZUR_ID:
            self._добавить_системное("[звонок] Выбери человека для звонка")
            return
        self._добавить_системное("[звонок] Гудки...")
        self.ws.send(pack(CALL_OFFER, to=self.текущий_peer))

    def _входящий_звонок(self, данные):
        from_ = данные.get("from")
        self._добавить_системное(f"[звонок] Входящий от {self.контакты.get(from_, '?')}. Пиши 'да' чтобы принять.")
        self._pending_call_from = from_
        self.ws.send(pack(CALL_ANSWER, to=from_))
        self.call_active = True

    def _завершить_звонок(self):
        self.call_active = False
        self._добавить_системное("[звонок] Завершён.")

    def при_закрытии(self):
        self.ws_готов = False
        try:
            if self.ws: self.ws.close()
        except: pass
        self.destroy()

if __name__ == "__main__":
    app = StarchApp()
    app.protocol("WM_DELETE_WINDOW", app.при_закрытии)
    app.mainloop()