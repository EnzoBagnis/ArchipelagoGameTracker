#!/usr/bin/env python3
"""
Script de build — génère l'exécutable Windows (.exe)
Usage: python build.py
"""
import subprocess
import sys
import os
import shutil

def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "logo.ico")

    # Supprime les anciens builds pour forcer la mise à jour
    for folder in ["build", "dist", "__pycache__"]:
        full = os.path.join(script_dir, folder)
        if os.path.exists(full):
            shutil.rmtree(full)
            print(f"🗑️  Ancien dossier '{folder}' supprimé.")

    spec_file = os.path.join(script_dir, "ArchipelagoTracker.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print("🗑️  Ancien .spec supprimé.")

    print("\n📦 Installation de PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "pyinstaller", "requests", "--quiet"])

    print("🔨 Compilation en .exe...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "ArchipelagoTracker",
    ]

    if os.path.exists(icon_path):
        cmd += ["--icon", icon_path]
        cmd += ["--add-data", f"{icon_path};."]
        print("🎨 Icône logo.ico incluse.")
    else:
        print("⚠️  logo.ico non trouvé — .exe sans icône.")

    cmd.append("main.py")

    subprocess.check_call(cmd, cwd=script_dir)
    print("\n✅ Terminé ! → dist/ArchipelagoTracker.exe")

if __name__ == "__main__":
    build()