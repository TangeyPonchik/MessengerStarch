"""
release.py — Автоматический релиз-менеджер Starch.
Запуск: python release.py
"""

import os
import sys
import shutil
import zipfile
import subprocess
from datetime import datetime

# UTF-8 для консоли Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(ROOT, "version.txt")

# ИЗМЕНЕНО: Путь к бэкапам на "Мой диск"
BACKUP_DIR = r"C:\Users\chagi\Мой диск\Starch_Backups"

REPO_NAME = "TangeyPonchik/MessengerStarch"

SKIP_DIRS = {".git", "__pycache__", "venv", "env", ".idea", ".vscode", "build", "dist", "Starch_Backups"}
SKIP_FILES = {"starch.db", "starch_session.json", "release.py", "version.txt"}

def ask(вопрос):
    return input(вопрос).strip()

def read_version():
    if not os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write("1.0.0")
        return "1.0.0"
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def bump_version(cur, тип):
    major, minor, patch = map(int, cur.split("."))
    if тип == "m":
        major += 1; minor = 0; patch = 0
    elif тип == "n":
        minor += 1; patch = 0
    elif тип == "f":
        patch += 1
    return f"{major}.{minor}.{patch}"

def update_version(new_ver):
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(new_ver)
    print(f"✅ Версия обновлена: {new_ver}")

def make_backup(version):
    print("\n💾 Создание ZIP-бэкапа на 'Мой диск'...")
    
    # Создаём папку, если её нет
    if not os.path.exists(BACKUP_DIR):
        try:
            os.makedirs(BACKUP_DIR)
        except Exception as e:
            print(f"❌ Не удалось создать папку {BACKUP_DIR}. Проверь, запущен ли Google Drive. Ошибка: {e}")
            return
            
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_name = f"Starch_v{version}_{now}.zip"
    zip_path = os.path.join(BACKUP_DIR, zip_name)

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(ROOT):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for file in files:
                    if file in SKIP_FILES:
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, ROOT)
                    zipf.write(file_path, arcname)
                    
        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        print(f"✅ Бэкап готов: {zip_path} ({size_mb:.2f} MB)")
    except Exception as e:
        print(f"❌ Ошибка при создании ZIP: {e}")

def run_cmd(cmd):
    try:
        subprocess.run(cmd, cwd=ROOT, check=True, shell=True)
        return True
    except subprocess.CalledProcessError:
        print(f"❌ Ошибка выполнения: {cmd}")
        return False

def main():
    print("============================================")
    print("   Starch · Релиз-менеджер")
    print("============================================\n")

    cur_version = read_version()
    print(f"Текущая версия: v{cur_version}")
    
    print("Тип обновления: m - мажор, n - минор, f - фикс")
    bump_type = ask("Тип (m/n/f): ").lower()
    
    if bump_type not in ["m", "n", "f"]:
        print("❌ Неверный тип")
        return

    new_version = bump_version(cur_version, bump_type)
    print(f"\nНовая версия: v{new_version}")
    
    if ask("Подтвердить? (y/n): ").lower() != "y":
        print("Отмена.")
        return

    # 1. Обновляем версию
    update_version(new_version)

    # 2. Бэкап
    if ask("\n💾 Сделать ZIP-бэкап перед релизом? (y/n): ").lower() == "y":
        make_backup(new_version)

    # 3. Git Commit & Push
    print("\n🚀 Отправка на GitHub...")
    commit_msg = ask("Введите commit message (что нового): ")
    if not commit_msg:
        commit_msg = f"Релиз v{new_version}"

    if not run_cmd("git add ."):
        return
    if not run_cmd(f'git commit -m "v{new_version}: {commit_msg}"'):
        print("⚠ Коммит не создан (возможно, нет изменений).")
    if not run_cmd("git push origin main"):
        print("❌ Ошибка Push. Проверь ветку (main или master) и доступ к репозиторию.")
        return

    print("✅ Код отправлен на GitHub!")

    # 4. GitHub Release
    if ask("\n🏷️ Создать релиз на GitHub через gh CLI? (y/n): ").lower() == "y":
        print("Тип релиза: 1 - Бета (Pre-release), 2 - Стабильный")
        rel_type = ask("Выбор (1/2): ")
        prerelease = "--prerelease" if rel_type == "1" else ""
        
        gh_cmd = f'gh release create v{new_version} --title "Starch v{new_version}" --notes "{commit_msg}" {prerelease}'
        print(f"\nВыполняю: {gh_cmd}")
        if run_cmd(gh_cmd):
            print("✅ Релиз успешно создан!")
        else:
            print("❌ Не удалось создать релиз. Установлен ли gh CLI?")
    else:
        print("Пропуск создания релиза.")

if __name__ == "__main__":
    main()