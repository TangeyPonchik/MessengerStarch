import sys, os, io, threading, time, asyncio
import requests, uvicorn

if sys.stdout is not None and sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr is not None and sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from server import app as fastapi_app
import database as db
from client import StarchApp

def start_server():
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=8000, log_level="info", loop="asyncio:SelectorEventLoop")
    server = uvicorn.Server(config)
    asyncio.run(server.serve())

if __name__ == "__main__":
    db.init_db()
    print("[Starch] База данных готова.")
    threading.Thread(target=start_server, daemon=True).start()
    
    print("[Starch] Ожидание сервера...")
    for попытка in range(15):
        try:
            if requests.get("http://127.0.0.1:8000/", timeout=1).status_code == 200:
                print(f"[Starch] Сервер готов (попытка {попытка + 1}).")
                break
        except: pass
        time.sleep(1)
    else:
        print("[Starch] ВНИМАНИЕ: Сервер не отвечает.")

    app = StarchApp()
    app.protocol("WM_DELETE_WINDOW", app.при_закрытии)
    app.mainloop()