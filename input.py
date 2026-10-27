import customtkinter as ctk
import sounddevice as sd
import soundfile as sf
import tempfile
import os

BG = "#17212b"
SIDEBAR = "#0e1621"
TEXT = "#ffffff"
MUTED = "#7d8e98"
ACCENT = "#4dabf7"

# ============================================================
# ЭМОДЗИ-ПИКЕР
# ============================================================
def открыть_эмодзи(родитель, поле_ввода):
    окно = ctk.CTkToplevel(родитель)
    окно.title("Эмодзи")
    окно.geometry("350x350")
    окно.configure(fg_color=BG)
    окно.attributes("-topmost", True)

    эмодзи = [
        "😀", "😂", "🤣", "😊", "😍", "🥰", "😎", "🤔", "😅", "😭",
        "😡", "🤬", "🤯", "🥳", "😴", "🤤", "🤢", "🤮", "🤧", "🥵",
        "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "💔", "💕",
        "👍", "👎", "👌", "✌️", "🤞", "🤝", "🙏", "💪", "👏", "🙌",
        "🔥", "⭐", "✨", "💯", "🎉", "🎊", "🎈", "🎁", "🏆", "🥇",
        "🍕", "🍔", "🍟", "🌭", "🍿", "🧂", "🥓", "🍗", "🍖", "🍤",
        "🐱", "🐶", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯",
        "🚀", "✈️", "🚗", "🚕", "🚌", "🚑", "🚓", "🚒", "🚜", "🚲",
        "🌍", "🌎", "🌏", "🌕", "🌙", "⭐", "🌟", "☀️", "🌤️", "⛅",
    ]

    сетка = ctk.CTkScrollableFrame(окно, fg_color="transparent")
    сетка.pack(fill="both", expand=True, padx=10, pady=10)

    def _выбрать(э):
        поле_ввода.insert("end", э)
        окно.destroy()

    for i, э in enumerate(эмодзи):
        btn = ctk.CTkButton(сетка, text=э, width=40, height=40,
                            font=("Segoe UI", 20), fg_color="#2b5278",
                            hover_color="#3b6b98",
                            command=lambda e=э: _выбрать(e))
        btn.grid(row=i // 7, column=i % 7, padx=2, pady=2)

# ============================================================
# ЗАПИСЬ ГОЛОСА
# ============================================================
class ЗаписьГолоса(ctk.CTkToplevel):
    def __init__(self, родитель, callback_готово):
        super().__init__(родитель)
        self.title("Голосовое сообщение")
        self.geometry("300x200")
        self.configure(fg_color=BG)
        self.attributes("-topmost", True)
        self.callback_готово = callback_готово
        self.запись_идёт = False
        self.файл = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        
        self.лейбл = ctk.CTkLabel(self, text="🔴 Нажми, чтобы начать запись", font=("Segoe UI", 14), text_color=TEXT)
        self.лейбл.pack(pady=20)

        self.кнопка = ctk.CTkButton(self, text="⏺ Записать", fg_color="#e03131", hover_color="#c92a2a", height=40, command=self.записать)
        self.кнопка.pack(pady=10)

        self.отправить_btn = ctk.CTkButton(self, text="➤ Отправить", fg_color=ACCENT, height=40, state="disabled", command=self.отправить)
        self.отправить_btn.pack(pady=10)

    def записать(self):
        if not self.запись_идёт:
            self.запись_идёт = True
            self.кнопка.configure(text="⏹ Стоп", fg_color="#555")
            self.лейбл.configure(text="🎤 Запись...")
            try:
                self.stream = sd.InputStream(samplerate=44100, channels=1, callback=self._аудио_callback)
                self.stream.start()
                self._аудио_данные = []
            except Exception as e:
                self.лейбл.configure(text=f"Ошибка микрофона: {e}")
                self.запись_идёт = False
        else:
            self.запись_идёт = False
            self.stream.stop()
            self.stream.close()
            sf.write(self.файл, self._аудио_данные, 44100)
            self.кнопка.configure(text="✅ Записано", state="disabled")
            self.отправить_btn.configure(state="normal")
            self.лейбл.configure(text="Готово! Можно отправить.")

    def _аудио_callback(self, indata, frames, time, status):
        if self.запись_идёт:
            self._аудио_данные.append(indata.copy())

    def отправить(self):
        self.callback_готово(self.файл)
        self.destroy()

# ============================================================
# ПАНЕЛЬ ВВОДА (вынесена из client.py)
# ============================================================
def создать_панель_ввода(родитель, app_instance):
    """
    Создает панель ввода и привязывает её к методам приложения.
    app_instance должен иметь методы: _по_enter, _печатаю, _отправить, _выбрать_картинку, _записать_голос.
    """
    ввод_рамка = ctk.CTkFrame(родитель, fg_color=BG)
    ввод_рамка.pack(fill="x", padx=10, pady=(0, 10))

    поле = ctk.CTkEntry(ввод_рамка, height=45, font=("Segoe UI", 13), placeholder_text="Сообщение...", fg_color=SIDEBAR, border_width=0)
    поле.pack(side="left", fill="x", expand=True, padx=(0, 8))
    поле.bind("<Return>", app_instance._по_enter)
    поле.bind("<KeyRelease>", app_instance._печатаю)

    ctk.CTkButton(ввод_рамка, text="😊", width=45, height=45, font=("Segoe UI", 18), fg_color="#2b5278", command=lambda: открыть_эмодзи(родитель, поле)).pack(side="right", padx=(0, 5))
    ctk.CTkButton(ввод_рамка, text="🖼️", width=45, height=45, font=("Segoe UI", 18), fg_color="#2b5278", command=app_instance._выбрать_картинку).pack(side="right", padx=(0, 5))
    ctk.CTkButton(ввод_рамка, text="🎤", width=45, height=45, font=("Segoe UI", 18), fg_color="#e03131", command=app_instance._записать_голос).pack(side="right", padx=(0, 5))
    ctk.CTkButton(ввод_рамка, text="➤", width=50, height=45, font=("Segoe UI", 20, "bold"), fg_color=ACCENT, command=app_instance._отправить).pack(side="right")

    return поле