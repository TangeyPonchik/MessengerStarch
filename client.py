"""
client.py — Starch на CustomTkinter.
Запуск: python client.py
"""

import customtkinter as ctk
import threading
import queue
import json
import os
import time
import requests
import websocket

from protocol import (
    pack, unpack, MSG, SYS, ONLINE, TYPING, READ, EDIT, DELETE,
    REACTION, PING, HISTORY, AUTH_OK, SEARCH,
)

SERVER_HTTP = "http://127.0.0.1:8000"
SERVER_WS = "ws://127.0.0.1:8000/ws"
SESSION_FILE = "starch_session.json"

LAZUR_ID = 999
LAZUR_NAME = "Lazur-lite"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#17212b"
SIDEBAR = "#0e1621"
ACTIVE_CHAT = "#2b5278"
BUBBLE_OWN = "#2b5278"
BUBBLE_OTHER = "#182533"
BUBBLE_LAZUR = "#3a2a5a"
TEXT = "#ffffff"
MUTED = "#7d8e98"
ACCENT = "#4dabf7"
LAZUR_COLOR = "#b794f6"


class StarchApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Starch")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(fg_color=BG)

        self.token = None
        self.user_id = None
        self.username = None
        self.ws = None
        self.ws_готов = False
        self.очередь = queue.Queue()
        self._последний_typing = 0
        self._переподключение_идёт = False

        self.текущий_peer = None
        self.контакты = {}
        self.чат_метки = {}
        self.пользователи_онлайн = set()

        self._экран_логина()
        self._экран_чата()
        self._показать_логин()

        self.after(100, self._попробовать_восстановить)

    # ============ ЛОГИН ============
    def _экран_логина(self):
        self.логин = ctk.CTkFrame(self, fg_color=BG)
        центр = ctk.CTkFrame(self.логин, fg_color="transparent")
        центр.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(центр, text="Starch", font=("Segoe UI", 56, "bold"),
                     text_color=ACCENT).pack(pady=(0, 6))
        ctk.CTkLabel(центр, text="Безопасный чат на Python",
                     font=("Segoe UI", 14), text_color=MUTED).pack(pady=(0, 30))

        self.ник_поле = ctk.CTkEntry(центр, placeholder_text="Логин",
                                     height=45, width=320, font=("Segoe UI", 16))
        self.ник_поле.pack(pady=6)

        self.пароль_поле = ctk.CTkEntry(центр, placeholder_text="Пароль",
                                        height=45, width=320, font=("Segoe UI", 16),
                                        show="*")
        self.пароль_поле.pack(pady=6)
        self.пароль_поле.bind("<Return>", lambda e: self._войти())

        рамка = ctk.CTkFrame(центр, fg_color="transparent")
        рамка.pack(pady=10)

        ctk.CTkButton(рамка, text="Войти", height=45, width=155,
                      font=("Segoe UI", 16, "bold"), fg_color=ACCENT,
                      command=self._войти).pack(side="left", padx=4)
        ctk.CTkButton(рамка, text="Регистрация", height=45, width=155,
                      font=("Segoe UI", 16), fg_color="#2b5278",
                      command=self._регистрация).pack(side="left", padx=4)

        self.статус_логина = ctk.CTkLabel(центр, text="", font=("Segoe UI", 12),
                                          text_color="#f44")
        self.статус_логина.pack(pady=10)

    # ============ ЧАТ ============
    def _экран_чата(self):
        self.чат = ctk.CTkFrame(self, fg_color=BG)

        self.sidebar = ctk.CTkFrame(self.чат, width=260, fg_color=SIDEBAR,
                                    corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="Starch",
                     font=("Segoe UI", 22, "bold"), text_color=ACCENT
                     ).pack(pady=(20, 5), padx=15, anchor="w")

        self.я_лейбл = ctk.CTkLabel(self.sidebar, text="",
                                    font=("Segoe UI", 12), text_color=MUTED)
        self.я_лейбл.pack(padx=15, anchor="w", pady=(0, 15))

        ctk.CTkLabel(self.sidebar, text="ЧАТЫ",
                     font=("Segoe UI", 10, "bold"), text_color=MUTED
                     ).pack(padx=15, pady=(5, 5), anchor="w")

        self.контакты_рамка = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.контакты_рамка.pack(fill="both", expand=True, padx=5, pady=5)

        self.main = ctk.CTkFrame(self.чат, fg_color=BG, corner_radius=0)
        self.main.pack(side="right", fill="both", expand=True)

        self.шапка = ctk.CTkFrame(self.main, height=60, fg_color=SIDEBAR,
                                  corner_radius=0)
        self.шапка.pack(fill="x")
        self.шапка.pack_propagate(False)

        self.шапка_название = ctk.CTkLabel(self.шапка, text="Общий чат",
                                           font=("Segoe UI", 18, "bold"),
                                           text_color=TEXT)
        self.шапка_название.pack(side="left", padx=20, pady=15)

        self.шапка_статус = ctk.CTkLabel(self.шапка, text="",
                                         font=("Segoe UI", 11), text_color=MUTED)
        self.шапка_статус.pack(side="left", padx=10)

        self.поиск_поле = ctk.CTkEntry(self.шапка, placeholder_text="🔍 Поиск",
                                       width=180, height=32, font=("Segoe UI", 12),
                                       fg_color=BG, border_width=1)
        self.поиск_поле.pack(side="right", padx=15)
        self.поиск_поле.bind("<Return>", self._поиск)

        self.история = ctk.CTkScrollableFrame(self.main, fg_color=BG)
        self.история.pack(fill="both", expand=True, padx=10, pady=10)

        self.печатает_лейбл = ctk.CTkLabel(self.main, text="",
                                           font=("Segoe UI", 11, "italic"),
                                           text_color=MUTED)
        self.печатает_лейбл.pack(padx=20, anchor="w")

        ввод_рамка = ctk.CTkFrame(self.main, fg_color=BG)
        ввод_рамка.pack(fill="x", padx=10, pady=(0, 10))

        self.поле = ctk.CTkEntry(
            ввод_рамка, height=45, font=("Segoe UI", 13),
            placeholder_text="Напиши сообщение или вызови ИИ-Бота написав @lazur-lite вначале сообщения",
            fg_color=SIDEBAR, border_width=0,
        )
        self.поле.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.поле.bind("<Return>", self._по_enter)
        self.поле.bind("<KeyRelease>", self._печатаю)

        ctk.CTkButton(ввод_рамка, text="➤", width=50, height=45,
                      font=("Segoe UI", 20, "bold"), fg_color=ACCENT,
                      command=self._отправить).pack(side="right")

        self.reply_баннер = None
        self.reply_to = None

    # ============ СЕССИЯ ============
    def _сохранить_сессию(self):
        try:
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump({"token": self.token, "user_id": self.user_id,
                           "username": self.username}, f, ensure_ascii=False)
        except Exception as e:
            print(f"Не сохранил сессию: {e}")

    def _попробовать_восстановить(self):
        if not os.path.exists(SESSION_FILE):
            return
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                данные = json.load(f)
            self.token = данные["token"]
            self.user_id = данные["user_id"]
            self.username = данные["username"]
            threading.Thread(target=self._подключиться, daemon=True).start()
        except Exception as e:
            print(f"Не восстановил сессию: {e}")

    def _показать_логин(self):
        self.чат.pack_forget()
        self.логин.pack(fill="both", expand=True)

    def _показать_чат(self):
        self.логин.pack_forget()
        self.чат.pack(fill="both", expand=True)
        self.поле.focus_set()
        self.я_лейбл.configure(text=f"@{self.username}")
        self._обновить_контакты()
        self.after(150, lambda: self._запросить_историю(None))

    # ============ АВТОРИЗАЦИЯ ============
    def _войти(self):
        self._авторизация("/login")

    def _регистрация(self):
        self._авторизация("/register")

    def _авторизация(self, endpoint):
        логин = self.ник_поле.get().strip()
        пароль = self.пароль_поле.get().strip()
        if not логин or not пароль:
            self.статус_логина.configure(text="Заполни оба поля", text_color="#f44")
            return
        self.статус_логина.configure(text="...", text_color="#fa0")
        threading.Thread(target=self._http_auth,
                         args=(endpoint, логин, пароль), daemon=True).start()

    def _http_auth(self, endpoint, логин, пароль):
        try:
            r = requests.post(SERVER_HTTP + endpoint,
                              json={"username": логин, "password": пароль},
                              timeout=10)
            if r.status_code != 200:
                try:
                    detail = r.json().get("detail", "Ошибка")
                except Exception:
                    detail = f"HTTP {r.status_code}"
                self.after(0, lambda: self.статус_логина.configure(
                    text=detail, text_color="#f44"))
                return
            данные = r.json()
            self.token = данные["token"]
            self.user_id = данные["user_id"]
            self.username = данные["username"]
            self._сохранить_сессию()
            threading.Thread(target=self._подключиться, daemon=True).start()
        except Exception as e:
            self.after(0, lambda: self.статус_логина.configure(
                text=f"Сервер недоступен: {e}", text_color="#f44"))

    # ============ СЕТЬ ============
    def _подключиться(self):
        try:
            self.ws = websocket.create_connection(f"{SERVER_WS}/{self.token}")
            self.ws_готов = True
            threading.Thread(target=self._читатель, daemon=True).start()
            self.after(50, self._разобрать_очередь)
            self.after(0, self._показать_чат)
        except Exception as e:
            print(f"Подключение: {e}")
            self.after(0, lambda: self.статус_логина.configure(
                text=f"WebSocket: {e}", text_color="#f44"))
            if self.token:
                self.after(3000, self._переподключиться)

    def _читатель(self):
        while self.ws_готов:
            try:
                msg = self.ws.recv()
                if not msg:
                    break
                self.очередь.put(msg)
            except Exception:
                break
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
        except queue.Empty:
            pass
        if self.ws_готов:
            self.after(50, self._разобрать_очередь)

    def _переподключиться(self):
        self._переподключение_идёт = False
        if self.ws_готов or not self.token:
            return
        try:
            self.шапка_статус.configure(text="переподключение...", text_color="#fa0")
        except Exception:
            pass
        threading.Thread(target=self._подключиться_заново, daemon=True).start()

    def _подключиться_заново(self):
        try:
            self.ws = websocket.create_connection(f"{SERVER_WS}/{self.token}")
            self.ws_готов = True
            threading.Thread(target=self._читатель, daemon=True).start()
            self.after(50, self._разобрать_очередь)
            self.after(0, lambda: self.шапка_статус.configure(
                text="online", text_color="#4f4"))
            self.after(100, lambda: self._запросить_историю(self.текущий_peer))
        except Exception as e:
            print(f"Переподключение: {e}")
            if not self._переподключение_идёт:
                self._переподключение_идёт = True
                self.after(5000, self._переподключиться)

    def _обработать(self, д):
        тип = д.get("тип")

        if тип == PING:
            try:
                self.ws.send(pack(PING))
            except Exception:
                pass
            return

        if тип == AUTH_OK:
            return

        if тип == ONLINE:
            self.пользователи_онлайн = set(д.get("users", []))
            print(f"[DEBUG] ONLINE: {self.пользователи_онлайн}")
            self._обновить_контакты()

        elif тип == HISTORY:
            peer = д.get("peer")
            if peer != self.текущий_peer:
                return
            for виджет in self.история.winfo_children():
                виджет.destroy()
            self.чат_метки.clear()
            for m in д.get("messages", []):
                self._нарисовать_сообщение(m)

        elif тип == SEARCH:
            peer = д.get("peer")
            if peer != self.текущий_peer:
                return
            for виджет in self.история.winfo_children():
                виджет.destroy()
            self.чат_метки.clear()
            результаты = д.get("результаты", [])
            if not результаты:
                self._системное(f"🔍 Ничего не найдено по «{д.get('запрос', '')}»")
            else:
                self._системное(f"🔍 Найдено: {len(результаты)}")
                for m in результаты:
                    self._нарисовать_сообщение(m)

        elif тип == MSG:
            from_id = д.get("from_id")
            from_name = д.get("from_name")

            if from_id and from_id != self.user_id and from_id != LAZUR_ID:
                if from_id not in self.контакты:
                    self.контакты[from_id] = from_name
                    self._обновить_контакты()

            to_user = д.get("to_user")
            свой = (from_id == self.user_id)

            if to_user is None:
                if self.текущий_peer is None:
                    self._нарисовать_сообщение(д)
            elif self.текущий_peer == (from_id if not свой else to_user):
                self._нарисовать_сообщение(д)
            elif not свой:
                self._обновить_контакты()

        elif тип == TYPING:
            if д.get("from_id") == self.текущий_peer:
                self.печатает_лейбл.configure(
                    text=f"{д.get('from_name')} печатает...")
                self.after(2000, lambda: self.печатает_лейбл.configure(text=""))

        elif тип == EDIT:
            mid = д.get("id")
            if mid in self.чат_метки:
                try:
                    self.чат_метки[mid].configure(text=д.get("текст", ""))
                except Exception:
                    pass

        elif тип == DELETE:
            mid = д.get("id")
            if mid in self.чат_метки:
                try:
                    self.чат_метки[mid].destroy()
                except Exception:
                    pass
                self.чат_метки.pop(mid, None)

    # ============ UI ============
    def _обновить_контакты(self):
        for w in self.контакты_рамка.winfo_children():
            w.destroy()

        self._кнопка_контакта(None, "Общий чат", online=True)
        self._кнопка_контакта(LAZUR_ID, f"🤖 {LAZUR_NAME}", online=True)

        for uid, name in sorted(self.контакты.items(), key=lambda x: x[1]):
            if uid == LAZUR_ID:
                continue
            self._кнопка_контакта(uid, name, online=uid in self.пользователи_онлайн)

    def _кнопка_контакта(self, peer, name, online):
        активен = peer == self.текущий_peer
        цвет = ACTIVE_CHAT if активен else "transparent"
        btn = ctk.CTkButton(
            self.контакты_рамка,
            text=("● " if online else "○ ") + name,
            anchor="w", fg_color=цвет, hover_color="#1c2b3a",
            font=("Segoe UI", 14), height=40, corner_radius=8,
            text_color=TEXT if online else MUTED,
            command=lambda: self._выбрать_чат(peer, name))
        btn.pack(fill="x", pady=2, padx=4)

    def _выбрать_чат(self, peer, name):
        self.текущий_peer = peer
        self.шапка_название.configure(text=name)
        self.шапка_статус.configure(
            text="online" if (peer is None or peer == LAZUR_ID
                              or peer in self.пользователи_онлайн)
            else "offline")
        for w in self.история.winfo_children():
            w.destroy()
        self.чат_метки.clear()
        self._обновить_контакты()
        self._запросить_историю(peer)

    def _запросить_историю(self, peer):
        if self.ws_готов:
            try:
                self.ws.send(pack(HISTORY, peer=peer))
            except Exception:
                pass

    def _системное(self, текст):
        метка = ctk.CTkLabel(self.история, text=текст,
                             font=("Segoe UI", 11, "italic"), text_color=MUTED)
        метка.pack(pady=4, padx=8)

    def _нарисовать_сообщение(self, m):
        свой = (m.get("from_id") == self.user_id)
        from_lazur = (m.get("from_id") == LAZUR_ID)
        автор = m.get("from_name", "?")
        текст = m.get("текст", "")
        время = m.get("время", "")
        edited = m.get("edited", 0)

        строка = ctk.CTkFrame(self.история, fg_color="transparent")
        строка.pack(fill="x", pady=3, padx=8)

        if from_lazur:
            bg = BUBBLE_LAZUR
        elif свой:
            bg = BUBBLE_OWN
        else:
            bg = BUBBLE_OTHER

        bubble = ctk.CTkFrame(строка, fg_color=bg, corner_radius=12)
        bubble.pack(side="right" if свой else "left")

        if not свой:
            ctk.CTkLabel(bubble, text=автор,
                         font=("Segoe UI", 11, "bold"),
                         text_color=LAZUR_COLOR if from_lazur else ACCENT
                         ).pack(anchor="w", padx=10, pady=(6, 0))

        текст_метка = ctk.CTkLabel(bubble, text=текст, font=("Segoe UI", 14),
                                   text_color=TEXT, anchor="w", justify="left",
                                   wraplength=500)
        текст_метка.pack(anchor="w", padx=10, pady=(2, 2))
        self.чат_метки[m.get("id")] = текст_метка

        низ = ctk.CTkLabel(bubble,
                           text=(f"{время} · изм." if edited else время),
                           font=("Segoe UI", 9), text_color=MUTED)
        низ.pack(anchor="e", padx=10, pady=(0, 6))

        if not from_lazur:
            def _меню(event):
                self._контекст_меню(m, свой, текст_метка)
            bubble.bind("<Button-3>", _меню)
            текст_метка.bind("<Button-3>", _меню)

        self._прокрутить_вниз()

    def _прокрутить_вниз(self):
        try:
            self.история._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _контекст_меню(self, m, свой, метка):
        from tkinter import Menu
        меню = Menu(self, tearoff=0)
        мид = m.get("id")

        реакции = Menu(меню, tearoff=0)
        for emoji in ["👍", "❤️", "😂", "😮", "😢", "🔥"]:
            реакции.add_command(label=emoji,
                                command=lambda e=emoji: self._реакция(мид, e))
        меню.add_cascade(label="Реакция", menu=реакции)

        if свой:
            меню.add_separator()
            меню.add_command(label="Редактировать",
                             command=lambda: self._редактировать(мид, метка))
            меню.add_command(label="Удалить",
                             command=lambda: self._удалить(мид))
        else:
            меню.add_separator()
            меню.add_command(label="Ответить",
                             command=lambda: self._ответить(m))

        меню.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def _реакция(self, mid, emoji):
        if self.ws_готов:
            try:
                self.ws.send(pack(REACTION, id=mid, emoji=emoji))
            except Exception:
                pass

    def _редактировать(self, mid, метка):
        from tkinter import simpledialog
        новое = simpledialog.askstring("Редактировать", "Новый текст:",
                                       initialvalue=метка.cget("text"))
        if новое:
            try:
                self.ws.send(pack(EDIT, id=mid, текст=новое))
            except Exception:
                pass

    def _удалить(self, mid):
        try:
            self.ws.send(pack(DELETE, id=mid))
        except Exception:
            pass

    def _ответить(self, m):
        self.reply_to = m.get("id")
        if self.reply_баннер:
            self.reply_баннер.destroy()
        self.reply_баннер = ctk.CTkLabel(
            self.main,
            text=f"↩ {m.get('from_name')}: {m.get('текст', '')[:50]}   ✕",
            font=("Segoe UI", 11), text_color=MUTED,
            fg_color=SIDEBAR, height=25)
        self.reply_баннер.pack(fill="x", padx=10, pady=(0, 4))
        self.reply_баннер.bind("<Button-1>", lambda e: self._отмена_reply())

    def _отмена_reply(self):
        self.reply_to = None
        if self.reply_баннер:
            self.reply_баннер.destroy()
            self.reply_баннер = None

    def _поиск(self, event=None):
        запрос = self.поиск_поле.get().strip()
        if not запрос:
            self._запросить_историю(self.текущий_peer)
            return
        if self.ws_готов:
            try:
                self.ws.send(pack(SEARCH, peer=self.текущий_peer, запрос=запрос))
            except Exception:
                pass

    # ============ ВВОД ============
    def _по_enter(self, event):
        self._отправить()
        return "break"

    def _печатаю(self, event=None):
        if not self.ws_готов or not self.текущий_peer:
            return
        сейчас = time.time()
        if сейчас - self._последний_typing < 2:
            return
        self._последний_typing = сейчас
        try:
            self.ws.send(pack(TYPING, to=self.текущий_peer))
        except Exception:
            pass

    def _отправить(self):
        if not self.ws_готов:
            return
        текст = self.поле.get().strip()
        if not текст:
            return
        try:
            self.ws.send(pack(MSG, to=self.текущий_peer, текст=текст,
                              reply_to=self.reply_to))
            self.поле.delete(0, "end")
            self._отмена_reply()
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            self.ws_готов = False
            try:
                self.шапка_статус.configure(text="offline", text_color="#f44")
            except Exception:
                pass
            if not self._переподключение_идёт:
                self._переподключение_идёт = True
                self.after(3000, self._переподключиться)

    def при_закрытии(self):
        self.ws_готов = False
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    import traceback
    try:
        app = StarchApp()
        app.protocol("WM_DELETE_WINDOW", app.при_закрытии)
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("Нажми Enter, чтобы выйти...")