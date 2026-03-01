import tkinter as tk
from tkinter import ttk, font
import requests
import csv
import io
import json
import os
import sys
import threading
import time
import webbrowser
import re
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
SHEET_ID = "1iuzDTOAvdoNe8Ne8i461qGNucg5OuEoF-Ikqs8aUQZw"
TABS = {
    "Playable Worlds": "58422002",
    "Core Verified":   "1675722515",
}

POPTRACKER_API = (
    "https://archipelago.miraheze.org/w/api.php"
    "?action=query&list=categorymembers"
    "&cmtitle=Category:Games_with_PopTracker"
    "&cmlimit=500&format=json"
)

GITHUB_REPO_RE = re.compile(
    r'https?://(?:www\.)?github\.com/([^/\s]+)/([^/\s#?]+)'
)

def get_cache_path():
    if os.name == "nt":
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                            "ArchipelagoTracker")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config", "ArchipelagoTracker")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "archipelago_cache.json")

CACHE_FILE = get_cache_path()

SKIP_NAMES = {
    "Game", "Do not sort",
    "Headers are locked to prevent auto-sorts from being done",
    "If something is missing, leave a comment!"
}

# ── STATUS COLORS ─────────────────────────────────────────────────────────────
STATUS_COLORS = {
    "Stable":         "#4ade80",
    "Unstable":       "#fb923c",
    "In Review":      "#60a5fa",
    "Broken on Main": "#f87171",
    "APWorld Only":   "#c084fc",
    "Merged":         "#34d399",
}

STATUS_ORDER = {
    "Merged":         0,
    "In Review":      1,
    "Stable":         2,
    "Unstable":       3,
    "Broken on Main": 4,
    "APWorld Only":   5,
}

# ── DATA LOGIC ────────────────────────────────────────────────────────────────
def fetch_tab(tab_name, gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return []
    return list(csv.reader(io.StringIO(r.content.decode("utf-8"))))

def rows_to_dict(rows, tab_name=""):
    if not rows:
        return {}

    # ── Fixed column layout (confirmed from sheet structure) ──────────────
    # Playable Worlds : A=Game(0)  B=Status(1)  C=APWorld(2)  D=Notes(3)
    # Core Verified   : A=Game(0)  B=Notes(1)   (no APWorld column)
    if tab_name == "Core Verified":
        idx_name, idx_status, idx_apworld, idx_notes = 0, -1, -1, 1
    else:
        idx_name, idx_status, idx_apworld, idx_notes = 0, 1, 2, 3

    result = {}
    for row in rows:
        if len(row) <= idx_name:
            continue
        name = row[idx_name].strip()
        if not name or name in SKIP_NAMES or len(name) > 80:
            continue

        def _get(i):
            return row[i].strip() if i != -1 and i < len(row) else ""

        status  = _get(idx_status)
        apworld = _get(idx_apworld)
        notes   = _get(idx_notes)

        # Skip header/info rows
        if status.lower() in ("status", "game", "do not sort"):
            continue

        result[name] = {"status": status, "notes": notes, "apworld": apworld}
    return result

URL_PATTERN = re.compile(r'https?://\S+')

def extract_urls(text):
    return URL_PATTERN.findall(text)

def extract_github_repo(notes, apworld=""):
    """Extracts (owner, repo) from GitHub URLs in apworld then notes."""
    for text in (apworld, notes):   # apworld column takes priority
        if not text:
            continue
        for url in extract_urls(text):
            m = GITHUB_REPO_RE.search(url)
            if m:
                owner = m.group(1)
                repo  = m.group(2)
                if repo.endswith(".git"):
                    repo = repo[:-4]
                return owner, repo
    return None

def fetch_github_release(owner, repo):
    """Returns {tag, date, url} for the latest release, or None."""
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {
            "User-Agent": "ArchipelagoTracker/1.0",
            "Accept":     "application/vnd.github+json",
        }
        r = requests.get(api_url, timeout=10, headers=headers)
        if r.status_code == 404:
            r2 = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/tags",
                timeout=10, headers=headers)
            if r2.status_code == 200:
                tags = r2.json()
                if tags:
                    return {"tag": tags[0].get("name", ""), "date": "", "url": ""}
            return None
        if r.status_code != 200:
            return None
        data     = r.json()
        raw_date = data.get("published_at", "")
        return {
            "tag":  data.get("tag_name", ""),
            "date": raw_date[:10] if raw_date else "",
            "url":  data.get("html_url", ""),
        }
    except Exception:
        return None

def fetch_poptracker_games():
    try:
        headers = {"User-Agent": "ArchipelagoTracker/1.0"}
        r = requests.get(POPTRACKER_API, timeout=15, headers=headers)
        if r.status_code != 200:
            return set()
        data    = r.json()
        members = data.get("query", {}).get("categorymembers", [])
        names   = set()
        for m in members:
            names.add(_normalize(m.get("title", "")))
        return names
    except Exception:
        return set()

def _normalize(name):
    n = name.lower()
    for prefix in ["category:", "game:"]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    n = re.sub(r"[:\-_'\"!.,&()]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def match_poptracker(game_name, poptracker_set):
    norm = _normalize(game_name)
    if norm in poptracker_set:
        return True
    for pt in poptracker_set:
        if norm in pt or pt in norm:
            if len(norm) > 4 and len(pt) > 4:
                return True
    return False

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ── GUI ───────────────────────────────────────────────────────────────────────
BG        = "#0d1117"
BG2       = "#161b22"
BG3       = "#1f2937"
ACCENT    = "#7c3aed"
ACCENT2   = "#a855f7"
TEXT      = "#e2e8f0"
TEXT_DIM  = "#64748b"
BORDER    = "#30363d"
GREEN     = "#4ade80"
RED       = "#f87171"
YELLOW    = "#fbbf24"

SORT_ICONS = {
    None:  " -",
    True:  " ↑",
    False: " ↓",
}

class ArchipelagoTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Archipelago Tracker")
        self.geometry("1150x740")
        self.minsize(900, 600)
        self.configure(bg=BG)

        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
            self.iconbitmap(icon_path)
        except Exception:
            pass

        self._changes        = []
        self._all_games      = {}
        self._poptracker_set = set()
        self._releases       = {}
        self._filter_var     = tk.StringVar()
        self._tab_var        = tk.StringVar(value="Playable Worlds")
        self._status_filter  = tk.StringVar(value="All")
        self._pt_filter      = tk.StringVar(value="All")
        self._checking       = False

        self._sort_col = None
        self._sort_asc = None

        self._build_ui()
        self.after(200, self._load_initial)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = tk.Frame(self, bg=ACCENT, height=4)
        hdr.pack(fill="x")

        top = tk.Frame(self, bg=BG, pady=16, padx=20)
        top.pack(fill="x")

        tk.Label(top, text="⬡  ARCHIPELAGO TRACKER",
                 bg=BG, fg=TEXT,
                 font=("Courier New", 18, "bold")).pack(side="left")

        self._status_bar = tk.Label(top, text="Prêt", bg=BG, fg=TEXT_DIM,
                                    font=("Courier New", 10))
        self._status_bar.pack(side="right", padx=10)

        self._check_btn = tk.Button(top, text="⟳  Vérifier les mises à jour",
                                    command=self._start_check,
                                    bg=ACCENT, fg="white",
                                    font=("Courier New", 10, "bold"),
                                    relief="flat", padx=14, pady=6,
                                    cursor="hand2", activebackground=ACCENT2,
                                    activeforeground="white")
        self._check_btn.pack(side="right")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        # ── Left: Changes Panel ──────────────────────────────────────────────
        left = tk.Frame(body, bg=BG2, width=340)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        lhdr = tk.Frame(left, bg=BG2, pady=10, padx=14)
        lhdr.pack(fill="x")
        tk.Label(lhdr, text="DERNIERS CHANGEMENTS", bg=BG2,
                 fg=ACCENT2, font=("Courier New", 9, "bold")).pack(anchor="w")
        self._last_check_lbl = tk.Label(lhdr, text="Jamais vérifié",
                                        bg=BG2, fg=TEXT_DIM,
                                        font=("Courier New", 8))
        self._last_check_lbl.pack(anchor="w")

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x")

        changes_frame = tk.Frame(left, bg=BG2)
        changes_frame.pack(fill="both", expand=True)

        self._changes_canvas = tk.Canvas(changes_frame, bg=BG2,
                                         highlightthickness=0)
        changes_sb = ttk.Scrollbar(changes_frame, orient="vertical",
                                   command=self._changes_canvas.yview)
        self._changes_inner = tk.Frame(self._changes_canvas, bg=BG2)
        self._changes_inner.bind("<Configure>",
            lambda e: self._changes_canvas.configure(
                scrollregion=self._changes_canvas.bbox("all")))
        self._changes_canvas.create_window((0, 0), window=self._changes_inner,
                                           anchor="nw")
        self._changes_canvas.configure(yscrollcommand=changes_sb.set)
        self._changes_canvas.pack(side="left", fill="both", expand=True)
        changes_sb.pack(side="right", fill="y")
        self._changes_inner.bind_all("<MouseWheel>", self._on_mousewheel_changes)

        # ── Right: Games List ────────────────────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        fbar = tk.Frame(right, bg=BG3, pady=10, padx=14)
        fbar.pack(fill="x")

        for tab in TABS.keys():
            rb = tk.Radiobutton(fbar, text=tab, variable=self._tab_var,
                                value=tab, command=self._on_tab_change,
                                bg=BG3, fg=TEXT, selectcolor=BG3,
                                activebackground=BG3, activeforeground=ACCENT2,
                                font=("Courier New", 9, "bold"),
                                indicatoron=False, relief="flat",
                                padx=10, pady=4, cursor="hand2")
            rb.pack(side="left", padx=(0, 4))

        tk.Label(fbar, text="🔍", bg=BG3, fg=TEXT_DIM,
                 font=("Courier New", 11)).pack(side="left", padx=(16, 4))
        search_entry = tk.Entry(fbar, textvariable=self._filter_var,
                                bg=BG, fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=("Courier New", 10), width=20)
        search_entry.pack(side="left", ipady=4)
        self._filter_var.trace_add("write", lambda *a: self._refresh_table())

        tk.Label(fbar, text="  Statut:", bg=BG3, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left", padx=(12, 4))
        statuses = ["All"] + list(STATUS_COLORS.keys()) + ["Other"]
        ttk.Combobox(fbar, textvariable=self._status_filter, values=statuses,
                     state="readonly", width=13,
                     font=("Courier New", 9)).pack(side="left")
        self._status_filter.trace_add("write", lambda *a: self._refresh_table())

        tk.Label(fbar, text="  PopTracker:", bg=BG3, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left", padx=(12, 4))
        ttk.Combobox(fbar, textvariable=self._pt_filter,
                     values=["All", " Disponible", " Non disponible"],
                     state="readonly", width=16,
                     font=("Courier New", 9)).pack(side="left")
        self._pt_filter.trace_add("write", lambda *a: self._refresh_table())

        self._count_lbl = tk.Label(fbar, text="", bg=BG3, fg=TEXT_DIM,
                                   font=("Courier New", 9))
        self._count_lbl.pack(side="right", padx=8)

        # Table
        table_frame = tk.Frame(right, bg=BG)
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                         background=BG, foreground=TEXT,
                         rowheight=28, fieldbackground=BG,
                         borderwidth=0, font=("Courier New", 9))
        style.configure("Custom.Treeview.Heading",
                         background=BG3, foreground=ACCENT2,
                         font=("Courier New", 9, "bold"), relief="flat")
        style.map("Custom.Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "white")])
        style.map("Custom.Treeview.Heading",
                  background=[("active", ACCENT)],
                  foreground=[("active", "white")])

        cols = ("game", "status", "poptracker", "notes")
        self._tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", style="Custom.Treeview")

        self._tree.heading("game",       text="Jeu" + SORT_ICONS[None],
                           anchor="w",
                           command=lambda: self._on_sort_click("game"))
        self._tree.heading("status",     text="Statut" + SORT_ICONS[None],
                           anchor="w",
                           command=lambda: self._on_sort_click("status"))
        self._tree.heading("poptracker", text="PopTracker" + SORT_ICONS[None],
                           anchor="w",
                           command=lambda: self._on_sort_click("poptracker"))
        self._tree.heading("notes",      text="Notes", anchor="w")

        self._tree.column("game",       width=240, minwidth=140)
        self._tree.column("status",     width=120, minwidth=90)
        self._tree.column("poptracker", width=100, minwidth=80)
        self._tree.column("notes",      width=480, minwidth=180)

        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                             command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for status, color in STATUS_COLORS.items():
            self._tree.tag_configure(status, foreground=color)
        self._tree.tag_configure("Other",    foreground=TEXT_DIM)
        self._tree.tag_configure("new",      background="#1a2e1a")
        self._tree.tag_configure("core_yes", foreground=GREEN)
        self._tree.tag_configure("core_no",  foreground=RED)

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # ── Detail Panel ─────────────────────────────────────────────────────
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")

        detail = tk.Frame(right, bg=BG2, height=170)
        detail.pack(fill="x")
        detail.pack_propagate(False)

        detail_top = tk.Frame(detail, bg=BG2, padx=14, pady=8)
        detail_top.pack(fill="x")

        self._detail_title = tk.Label(detail_top,
                                      text="Cliquez sur un jeu pour voir les détails",
                                      bg=BG2, fg=TEXT_DIM,
                                      font=("Courier New", 10, "bold"), anchor="w")
        self._detail_title.pack(side="left", fill="x", expand=True)

        self._detail_status = tk.Label(detail_top, text="", bg=BG2, fg=TEXT,
                                       font=("Courier New", 9), anchor="e")
        self._detail_status.pack(side="right", padx=(8, 0))

        self._detail_pt = tk.Label(detail_top, text="", bg=BG2, fg=TEXT,
                                   font=("Courier New", 9), anchor="e")
        self._detail_pt.pack(side="right")

        detail_rel = tk.Frame(detail, bg=BG2, padx=14, pady=2)
        detail_rel.pack(fill="x")
        tk.Label(detail_rel, text="📦 Release:", bg=BG2, fg=TEXT_DIM,
                 font=("Courier New", 9), width=12, anchor="w").pack(side="left")
        self._detail_release = tk.Label(detail_rel, text="—", bg=BG2,
                                        fg=TEXT_DIM, font=("Courier New", 9),
                                        anchor="w")
        self._detail_release.pack(side="left")

        self._detail_notes = tk.Label(detail, text="", bg=BG2, fg=TEXT_DIM,
                                      font=("Courier New", 9), anchor="w",
                                      justify="left", wraplength=700, padx=14)
        self._detail_notes.pack(fill="x")

        self._links_frame = tk.Frame(detail, bg=BG2, padx=14, pady=4)
        self._links_frame.pack(fill="x")

    # ── Tab Change ────────────────────────────────────────────────────────────
    def _on_tab_change(self):
        self._sort_col = None
        self._sort_asc = None
        self._update_heading_icons()
        self._apply_columns()
        self._refresh_table()

    def _apply_columns(self):
        is_core = self._tab_var.get() == "Core Verified"
        if is_core:
            self._tree.column("status", width=0, minwidth=0, stretch=False)
            self._tree.heading("status", text="")
            self._tree.column("game",   width=280, minwidth=140)
            self._tree.column("notes",  width=530, minwidth=180)
        else:
            self._tree.column("status", width=120, minwidth=90, stretch=True)
            self._tree.heading("status", text="Statut" + SORT_ICONS[
                self._sort_asc if self._sort_col == "status" else None])
            self._tree.column("game",   width=240, minwidth=140)
            self._tree.column("notes",  width=480, minwidth=180)

    # ── Sort Logic ────────────────────────────────────────────────────────────
    def _on_sort_click(self, col):
        if col == "status" and self._tab_var.get() == "Core Verified":
            return
        if self._sort_col != col:
            self._sort_col = col
            self._sort_asc = True
        else:
            if self._sort_asc is True:
                self._sort_asc = False
            elif self._sort_asc is False:
                self._sort_col = None
                self._sort_asc = None
            else:
                self._sort_asc = True
                self._sort_col = col
        self._update_heading_icons()
        self._refresh_table()

    def _update_heading_icons(self):
        is_core = self._tab_var.get() == "Core Verified"
        cols_labels = {"game": "Jeu", "poptracker": "PopTracker"}
        if not is_core:
            cols_labels["status"] = "Statut"
        for col, label in cols_labels.items():
            icon = SORT_ICONS[self._sort_asc] if self._sort_col == col else SORT_ICONS[None]
            self._tree.heading(col, text=label + icon)

    def _sort_key(self, item):
        name, data, has_pt = item
        col = self._sort_col
        if col == "game":
            return name.lower()
        elif col == "status":
            return (STATUS_ORDER.get(data.get("status", ""), 99), name.lower())
        elif col == "poptracker":
            return (0 if has_pt else 1, name.lower())
        return name.lower()

    # ── Mouse wheel ───────────────────────────────────────────────────────────
    def _on_mousewheel_changes(self, event):
        self._changes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ── Initial Load ──────────────────────────────────────────────────────────
    def _load_initial(self):
        cache = load_cache()
        self._apply_columns()
        if cache:
            self._all_games      = cache
            self._poptracker_set = set(cache.get("_poptracker", []))
            self._releases       = cache.get("_releases", {})
            self._refresh_table()
            ts = cache.get("_timestamp", "")
            if ts:
                self._last_check_lbl.config(text=f"Dernier check: {ts}")
            total = sum(len(v) for k, v in cache.items()
                        if k not in ("_timestamp", "_poptracker", "_releases"))
            self._set_status(
                f"Cache chargé — {total} jeux")
        else:
            self._set_status("Aucun cache — Cliquez sur Vérifier !")

    # ── Check ─────────────────────────────────────────────────────────────────
    def _start_check(self):
        if self._checking:
            return
        self._checking = True
        self._check_btn.config(state="disabled", text="⟳  Vérification...")
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        cache        = load_cache()
        new_cache    = {"_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        changes      = []
        old_releases = cache.get("_releases", {})
        new_releases = {}

        for tab_name, gid in TABS.items():
            self._set_status(f"Récupération: {tab_name}...")
            rows = fetch_tab(tab_name, gid)
            if not rows:
                new_cache[tab_name]    = cache.get(tab_name, {})
                new_releases[tab_name] = old_releases.get(tab_name, {})
                continue

            current = rows_to_dict(rows, tab_name)
            old     = cache.get(tab_name, {})
            if isinstance(old, dict) and "_timestamp" in old:
                old = {}

            added    = {k: v for k, v in current.items() if k not in old}
            removed  = {k: v for k, v in old.items()     if k not in current}
            modified = {}
            for k in current:
                if k in old and isinstance(old[k], dict):
                    if old[k].get("status") != current[k]["status"]:
                        modified[k] = (old[k].get("status", "?"), current[k]["status"])

            for game, data in added.items():
                changes.append(("➕", tab_name, game, data["status"], "Ajouté", ""))
            for game in removed:
                changes.append(("➖", tab_name, game, "", "Retiré", ""))
            for game, (before, after) in modified.items():
                changes.append(("🔄", tab_name, game, after, f"{before} → {after}", ""))

            new_cache[tab_name] = current

            # GitHub release fetch — only for Playable Worlds
            old_tab_rels = old_releases.get(tab_name, {})
            new_tab_rels = {}
            if tab_name != "Core Verified":
                total = len(current)
                for idx, (game_name, game_data) in enumerate(current.items()):
                    self._set_status(
                        f"Releases {tab_name}: {idx+1}/{total} — {game_name[:28]}...")
                    notes   = game_data.get("notes",   "")
                    apworld = game_data.get("apworld", "")
                    repo    = extract_github_repo(notes, apworld)
                    if not repo:
                        if game_name in old_tab_rels:
                            new_tab_rels[game_name] = old_tab_rels[game_name]
                        continue
                    owner, repo_name = repo
                    release = fetch_github_release(owner, repo_name)
                    if not release:
                        if game_name in old_tab_rels:
                            new_tab_rels[game_name] = old_tab_rels[game_name]
                        continue
                    new_tab_rels[game_name] = release
                    old_tag = old_tab_rels.get(game_name, {}).get("tag", "")
                    new_tag = release.get("tag", "")
                    if new_tag and new_tag != old_tag:
                        desc = (f"Release: {old_tag} → {new_tag}"
                                if old_tag else f"Nouvelle release: {new_tag}")
                        changes.append((
                            "🏷️", tab_name, game_name, "",
                            desc, release.get("url", ""),
                        ))

            new_releases[tab_name] = new_tab_rels

        self._set_status("Récupération: PopTracker Wiki...")
        pt_set = fetch_poptracker_games()
        if pt_set:
            self._poptracker_set = pt_set
            new_cache["_poptracker"] = list(pt_set)
        else:
            self._poptracker_set = set(cache.get("_poptracker", []))
            new_cache["_poptracker"] = list(self._poptracker_set)

        new_cache["_releases"] = new_releases
        self._releases         = new_releases
        save_cache(new_cache)
        self._all_games = new_cache
        self._changes   = changes
        self.after(0, self._on_check_done)

    def _on_check_done(self):
        self._checking = False
        self._check_btn.config(state="normal", text="⟳  Vérifier les mises à jour")
        ts = self._all_games.get("_timestamp", "")
        self._last_check_lbl.config(text=f"Dernier check: {ts}")
        self._refresh_table()
        self._refresh_changes()
        n  = len(self._changes)
        pt = len(self._poptracker_set)
        self._set_status(f"✓ Check terminé — {n} changement(s) · {pt} jeux avec PopTracker")

    # ── Refresh Changes Panel ─────────────────────────────────────────────────
    def _refresh_changes(self):
        for w in self._changes_inner.winfo_children():
            w.destroy()

        if not self._changes:
            tk.Label(self._changes_inner, text="Aucun changement détecté",
                     bg=BG2, fg=TEXT_DIM, font=("Courier New", 9),
                     padx=14, pady=10).pack(anchor="w")
            return

        for entry in self._changes:
            icon    = entry[0]
            tab     = entry[1]
            game    = entry[2]
            status  = entry[3]
            desc    = entry[4]
            rel_url = entry[5] if len(entry) > 5 else ""

            row = tk.Frame(self._changes_inner, bg=BG2, pady=6, padx=14)
            row.pack(fill="x")
            top_row = tk.Frame(row, bg=BG2)
            top_row.pack(fill="x")
            tk.Label(top_row, text=icon, bg=BG2,
                     font=("Segoe UI Emoji", 11)).pack(side="left")
            tk.Label(top_row, text="  " + game, bg=BG2, fg=TEXT,
                     font=("Courier New", 9, "bold"),
                     wraplength=280, justify="left").pack(side="left")
            bot_row = tk.Frame(row, bg=BG2)
            bot_row.pack(fill="x")
            color = YELLOW if icon == "🏷️" else STATUS_COLORS.get(status, TEXT_DIM)
            tk.Label(bot_row, text="   " + tab + " — " + desc,
                     bg=BG2, fg=color, font=("Courier New", 8)).pack(side="left")
            if rel_url:
                lnk = tk.Label(bot_row, text=" ↗", bg=BG2, fg=ACCENT2,
                               font=("Courier New", 8, "underline"), cursor="hand2")
                lnk.pack(side="left")
                lnk.bind("<Button-1>", lambda e, u=rel_url: webbrowser.open(u))
            tk.Frame(self._changes_inner, bg=BORDER, height=1).pack(fill="x", padx=14)

    # ── Refresh Games Table ───────────────────────────────────────────────────
    def _refresh_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        tab   = self._tab_var.get()
        games = self._all_games.get(tab, {})
        if not isinstance(games, dict):
            return

        query     = self._filter_var.get().lower()
        sf        = self._status_filter.get()
        pt_filt   = self._pt_filter.get()
        new_names = {e[2] for e in self._changes if e[0] == "➕" and e[1] == tab}
        is_core   = tab == "Core Verified"

        filtered = []
        for name, data in games.items():
            if not isinstance(data, dict):
                continue
            status = data.get("status", "")
            notes  = data.get("notes",  "")
            has_pt = match_poptracker(name, self._poptracker_set)

            if query and query not in name.lower() \
                     and query not in status.lower() \
                     and query not in notes.lower():
                continue
            if sf != "All":
                if sf == "Other":
                    if status in STATUS_COLORS: continue
                elif status != sf:
                    continue
            if pt_filt == " Disponible"    and not has_pt: continue
            if pt_filt == " Non disponible" and has_pt:    continue

            filtered.append((name, data, has_pt))

        if self._sort_col is not None:
            filtered.sort(key=self._sort_key, reverse=(self._sort_asc is False))
        else:
            filtered.sort(key=lambda x: x[0].lower())

        for name, data, has_pt in filtered:
            status = data.get("status", "")
            notes  = data.get("notes",  "")
            pt_txt = "YES" if has_pt else "NO"

            if is_core:
                row_tag = "core_yes" if has_pt else "core_no"
            else:
                row_tag = status if status in STATUS_COLORS else "Other"

            tags = [row_tag] + (["new"] if name in new_names else [])
            self._tree.insert("", "end",
                              values=(name, status, pt_txt, notes),
                              tags=tags)

        self._count_lbl.config(text=f"{len(filtered)} jeux")

    # ── Detail Panel ─────────────────────────────────────────────────────────
    def _on_row_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if not values or len(values) < 4:
            return
        name, status, pt_txt, notes = values[0], values[1], values[2], values[3]
        tab = self._tab_var.get()

        self._detail_title.config(text=name, fg=TEXT)
        color = STATUS_COLORS.get(status, TEXT_DIM)
        self._detail_status.config(
            text="● " + status if status else "", fg=color)

        has_pt = match_poptracker(name, self._poptracker_set)
        if has_pt:
            wiki_url = "https://archipelago.miraheze.org/wiki/" + \
                       name.replace(" ", "_")
            self._detail_pt.config(text=" PopTracker: YES", fg=GREEN, cursor="hand2")
            self._detail_pt.bind("<Button-1>",
                lambda e, u=wiki_url: webbrowser.open(u))
        else:
            self._detail_pt.config(text=" PopTracker: NO", fg=RED, cursor="")
            self._detail_pt.unbind("<Button-1>")

        # ── Release info ──────────────────────────────────────────────────
        self._detail_release.unbind("<Button-1>")
        rel = self._releases.get(tab, {}).get(name)
        if rel and rel.get("tag"):
            tag_str  = rel["tag"]
            date_str = rel.get("date", "")
            rel_url  = rel.get("url", "")
            label    = (tag_str + "  —  " + date_str) if date_str else tag_str
            if rel_url:
                self._detail_release.config(
                    text=label + "  ↗", fg=ACCENT2,
                    font=("Courier New", 9, "underline"), cursor="hand2")
                self._detail_release.bind("<Button-1>",
                    lambda e, u=rel_url: webbrowser.open(u))
            else:
                self._detail_release.config(
                    text=label, fg=YELLOW, font=("Courier New", 9), cursor="")
        else:
            self._detail_release.config(
                text="—", fg=TEXT_DIM, font=("Courier New", 9), cursor="")

        labeled_links, plain_text = self._parse_notes(notes)
        self._detail_notes.config(text=plain_text if plain_text else "")

        for w in self._links_frame.winfo_children():
            w.destroy()

        if labeled_links:
            for label, url in labeled_links:
                row = tk.Frame(self._links_frame, bg=BG2)
                row.pack(anchor="w", pady=1)
                lbl_text = label if label else "🔗"
                tk.Label(row, text=lbl_text, bg=BG2, fg=TEXT_DIM,
                         font=("Courier New", 9),
                         width=16, anchor="w").pack(side="left")
                short = self._short_url(url)
                lnk = tk.Label(row, text=short, bg=BG2, fg=ACCENT2,
                               font=("Courier New", 9, "underline"),
                               cursor="hand2", anchor="w")
                lnk.pack(side="left")
                lnk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
                lnk.bind("<Enter>", lambda e, l=lnk: l.config(fg="#c084fc"))
                lnk.bind("<Leave>", lambda e, l=lnk: l.config(fg=ACCENT2))

    def _parse_notes(self, notes):
        if not notes:
            return [], ""
        labeled     = []
        plain_parts = []
        lines = notes.replace("\\n", "\n").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            urls_in_line = extract_urls(line)
            if not urls_in_line:
                plain_parts.append(line)
                continue
            for url in urls_in_line:
                before = line[:line.index(url)].strip().rstrip(":").strip()
                after  = line[line.index(url) + len(url):].strip()
                if after and not extract_urls(after):
                    plain_parts.append(after)
                labeled.append((before + (":" if before else ""), url))
        return labeled, " • ".join(plain_parts).strip()

    def _short_url(self, url):
        try:
            from urllib.parse import urlparse
            p    = urlparse(url)
            host = p.netloc.replace("www.", "")
            path = p.path[:35] + ("…" if len(p.path) > 35 else "")
            return host + path
        except Exception:
            return url[:50] + "…"

    # ── Status bar ────────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_bar.config(text=msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = ArchipelagoTracker()
    app.mainloop()