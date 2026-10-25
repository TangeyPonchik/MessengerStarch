"""
launcher.py — Запуск Starch (сервер + клиент) в одном окне.
"""

import sys
import os
import threading
import time
import asyncio
import io

import uvicorn

# Безопасная настройка кодировки
if sys.stdout is not None and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr is not None and sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Фикс для Windows: uvicorn в фоновом потоке требует SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Импортируем сервер (PyInstaller включит его в .exe)
from server import app as fastapi_app
import database as db

# Импортируем клиент
from client import StarchApp


def start_server():
    """Запускает uvicorn в фоновом потоке."""
    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=8000,
        log_level="critical",  # Чтобы не спамить в консоль
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())


if __name__ == "__main__":
    # 1. Инициализируем базу (создаём таблицы, если нет)
    db.init_db()

    # 2. Запускаем сервер в фоне
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # 3. Ждём, пока сервер поднимется
    print("Запуск Starch...")
    time.sleep(1.5)

    # 4. Запускаем клиент
    app = StarchApp()
    app.protocol("WM_DELETE_WINDOW", app.при_закрытии)
    app.mainloop()