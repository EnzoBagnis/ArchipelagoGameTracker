import subprocess
import sys
import os
import shutil
import glob

def choose_file(script_dir):
    py_files = glob.glob(os.path.join(script_dir, "*.py"))
    py_files = [f for f in py_files if os.path.basename(f) != "build.py"]

    if not py_files:
        print("!!! Aucun fichier .py trouvé dans le répertoire.")
        sys.exit(1)

    print("\n Fichiers Python disponibles :")
    for i, f in enumerate(py_files, 1):
        print(f"  [{i}] {os.path.basename(f)}")
    print("  [0] Entrer un chemin manuellement")

    while True:
        choice = input("\n Choisissez un fichier (numéro) : ").strip()
        if choice == "0":
            path = input(" Chemin du fichier : ").strip()
            if os.path.isfile(path) and path.endswith(".py"):
                return path
            print("!!  Fichier invalide ou introuvable.")
        elif choice.isdigit() and 1 <= int(choice) <= len(py_files):
            return py_files[int(choice) - 1]
        else:
            print("!!  Choix invalide, réessayez.")

def build():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(script_dir, "logo.ico")

    target_file = choose_file(script_dir)
    target_name = os.path.splitext(os.path.basename(target_file))[0]
    print(f"\n✅ Fichier sélectionné : {target_file}")

    # delete previous build artefacts, including any compiled bytecode
    for folder in ["build", "dist"]:
        full = os.path.join(script_dir, folder)
        if os.path.exists(full):
            shutil.rmtree(full)
            print(f"  Ancien dossier '{folder}' supprimé.")

    # remove all __pycache__ dirs in the tree so stale .pyc files can't sneak into
    # the PyInstaller archive (they would otherwise override the updated .py files)
    for root, dirs, files in os.walk(script_dir):
        if "__pycache__" in dirs:
            cache_dir = os.path.join(root, "__pycache__")
            shutil.rmtree(cache_dir)
            print(f"  Cache supprimé : {cache_dir}")

    spec_file = os.path.join(script_dir, f"{target_name}.spec")
    if os.path.exists(spec_file):
        os.remove(spec_file)
        print(f"  Ancien .spec supprimé.")

    print("\n Installation de PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "pyinstaller", "requests", "--quiet"])
    
    print(" Compilation en .exe...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", target_name,
    ]

    # include language resources so that translations remain available
    lang_dir = os.path.join(script_dir, "lang")
    if os.path.isdir(lang_dir):
        # use ; on Windows to separate source and dest when bundling data
        cmd += ["--add-data", f"{lang_dir};lang"]
        print(" Langue : dossier 'lang' inclus dans l'exécutable.")

    if os.path.exists(icon_path):
        cmd += ["--icon", icon_path]
        cmd += ["--add-data", f"{icon_path};."]
        print(" Icône logo.ico incluse.")
    else:
        print("!!  logo.ico non trouvé — .exe sans icône.")

    cmd.append(target_file)

    subprocess.check_call(cmd, cwd=script_dir)
    print(f"\n✅ Terminé ! → dist/{target_name}.exe")

if __name__ == "__main__":
    build()