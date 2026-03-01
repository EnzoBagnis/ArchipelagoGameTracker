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

def get_settings_path():
    return os.path.join(os.path.dirname(get_cache_path()), "settings.json")

def load_settings():
    p = get_settings_path()
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(data):
    with open(get_settings_path(), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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
    """Extracts (owner, repo) from GitHub URLs in apworld then notes.
    Ignores pull request URLs (/pull/) as they don't have releases.
    """
    for text in (apworld, notes):
        if not text:
            continue
        for url in extract_urls(text):
            m = GITHUB_REPO_RE.search(url)
            if m:
                owner = m.group(1)
                repo  = m.group(2)
                if repo.endswith(".git"):
                    repo = repo[:-4]
                # Skip pull request URLs — no releases there
                if "/pull/" in url:
                    continue
                return owner, repo
    return None

def fetch_github_release(owner, repo, token=""):
    """Returns {tag, date, url}, None on error, or 'rate_limited' on 403/429."""
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {
            "User-Agent": "ArchipelagoTracker/1.0",
            "Accept":     "application/vnd.github+json",
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        r = requests.get(api_url, timeout=10, headers=headers)
        if r.status_code in (403, 429):
            return "rate_limited"
        if r.status_code == 404:
            r2 = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/tags",
                timeout=10, headers=headers)
            if r2.status_code in (403, 429):
                return "rate_limited"
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

import unicodedata

def _normalize_steam(name):
    """Aggressive normalization for Steam↔sheet name matching."""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"\(.*?\)", "", name)   # remove (subtitle)
    name = re.sub(r":.*",     "", name)   # remove : subtitle
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name

def fetch_steam_owned(api_key, steam_ids):
    """Returns set of normalized game names owned across all given Steam IDs."""
    owned = {}
    headers = {"User-Agent": "ArchipelagoTracker/1.0"}
    for sid in steam_ids:
        sid = sid.strip()
        if not sid:
            continue
        try:
            r = requests.get(
                "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                params={"key": api_key, "steamid": sid, "include_appinfo": True},
                timeout=15, headers=headers)
            if r.status_code != 200:
                continue
            for game in r.json().get("response", {}).get("games", []):
                appid = game["appid"]
                if appid not in owned:
                    owned[appid] = game.get("name", "")
        except Exception:
            continue
    return {_normalize_steam(n) for n in owned.values() if n}
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
        self._steam_owned    = set()   # normalized Steam game names
        _s = load_settings()
        self._github_token    = _s.get("github_token", "")
        self._check_releases  = _s.get("check_releases", False)
        self._filter_var     = tk.StringVar()
        self._tab_var        = tk.StringVar(value="Playable Worlds")
        self._status_filter  = tk.StringVar(value="All")
        self._pt_filter      = tk.StringVar(value="All")
        self._owned_filter   = tk.StringVar(value="All")
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

        tk.Button(top, text="⚙", command=self._open_settings,
                  bg=BG, fg=TEXT_DIM,
                  font=("Courier New", 12), relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  activebackground=BG3, activeforeground=TEXT).pack(side="right", padx=(0, 4))

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

        tk.Label(fbar, text="  Owned:", bg=BG3, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left", padx=(12, 4))
        ttk.Combobox(fbar, textvariable=self._owned_filter,
                     values=["All", " YES", " NO"],
                     state="readonly", width=8,
                     font=("Courier New", 9)).pack(side="left")
        self._owned_filter.trace_add("write", lambda *a: self._refresh_table())

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

        cols = ("game", "status", "poptracker", "notes", "owned")
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
        self._tree.heading("owned",      text="Owned" + SORT_ICONS[None],
                           anchor="w",
                           command=lambda: self._on_sort_click("owned"))

        self._tree.column("game",       width=220, minwidth=130)
        self._tree.column("status",     width=120, minwidth=90)
        self._tree.column("poptracker", width=100, minwidth=80)
        self._tree.column("notes",      width=430, minwidth=160)
        self._tree.column("owned",      width=70,  minwidth=60)

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
            self._tree.column("game",   width=260, minwidth=140)
            self._tree.column("notes",  width=480, minwidth=180)
        else:
            self._tree.column("status", width=120, minwidth=90, stretch=True)
            self._tree.heading("status", text="Statut" + SORT_ICONS[
                self._sort_asc if self._sort_col == "status" else None])
            self._tree.column("game",   width=220, minwidth=130)
            self._tree.column("notes",  width=430, minwidth=160)

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
        cols_labels = {"game": "Jeu", "poptracker": "PopTracker", "owned": "Owned"}
        if not is_core:
            cols_labels["status"] = "Statut"
        for col, label in cols_labels.items():
            icon = SORT_ICONS[self._sort_asc] if self._sort_col == col else SORT_ICONS[None]
            self._tree.heading(col, text=label + icon)

    def _sort_key(self, item):
        name, data, has_pt, is_owned = item
        col = self._sort_col
        if col == "game":
            return name.lower()
        elif col == "status":
            return (STATUS_ORDER.get(data.get("status", ""), 99), name.lower())
        elif col == "poptracker":
            return (0 if has_pt else 1, name.lower())
        elif col == "owned":
            return (0 if is_owned else 1, name.lower())
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
            self._steam_owned    = set(cache.get("_steam_owned", []))
            self._refresh_table()
            ts = cache.get("_timestamp", "")
            if ts:
                self._last_check_lbl.config(text=f"Dernier check: {ts}")
            total = sum(len(v) for k, v in cache.items()
                        if k not in ("_timestamp", "_poptracker", "_releases"))
            self._set_status(
                f"Cache chargé — {total} jeux · {len(self._poptracker_set)} avec PopTracker")
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
        rate_limited = False

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
            if tab_name != "Core Verified" and not rate_limited and self._check_releases:
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
                    release = fetch_github_release(owner, repo_name, self._github_token)
                    if release == "rate_limited":
                        rate_limited = True
                        # Preserve all remaining cached releases for this tab
                        for k, v in old_tab_rels.items():
                            if k not in new_tab_rels:
                                new_tab_rels[k] = v
                        break
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
            else:
                # Rate limited or Core Verified — keep old release data intact
                new_tab_rels = dict(old_tab_rels)

            new_releases[tab_name] = new_tab_rels

        self._set_status("Récupération: PopTracker Wiki...")
        pt_set = fetch_poptracker_games()
        if pt_set:
            self._poptracker_set = pt_set
            new_cache["_poptracker"] = list(pt_set)
        else:
            self._poptracker_set = set(cache.get("_poptracker", []))
            new_cache["_poptracker"] = list(self._poptracker_set)

        # Steam owned — not fetched here, use cached value (refresh via ⚙)
        self._steam_owned = set(cache.get("_steam_owned", []))
        new_cache["_steam_owned"] = list(self._steam_owned)

        new_cache["_releases"] = new_releases
        self._releases         = new_releases
        save_cache(new_cache)
        self._all_games = new_cache
        self._changes   = changes
        self.after(0, lambda: self._on_check_done(rate_limited))

    def _on_check_done(self, rate_limited=False):
        self._checking = False
        self._check_btn.config(state="normal", text="⟳  Vérifier les mises à jour")
        ts = self._all_games.get("_timestamp", "")
        self._last_check_lbl.config(text=f"Dernier check: {ts}")
        self._refresh_table()
        self._refresh_changes()
        n  = len(self._changes)
        pt = len(self._poptracker_set)
        if rate_limited:
            self._set_status(
                "⚠ Limite GitHub atteinte — releases incomplètes. "
                "Ajoutez un token dans ⚙ Paramètres.")
        else:
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

        query       = self._filter_var.get().lower()
        sf          = self._status_filter.get()
        pt_filt     = self._pt_filter.get()
        owned_filt  = self._owned_filter.get()
        new_names   = {e[2] for e in self._changes if e[0] == "➕" and e[1] == tab}
        is_core     = tab == "Core Verified"

        filtered = []
        for name, data in games.items():
            if not isinstance(data, dict):
                continue
            status   = data.get("status", "")
            notes    = data.get("notes",  "")
            has_pt   = match_poptracker(name, self._poptracker_set)
            is_owned = _normalize_steam(name) in self._steam_owned

            if query and query not in name.lower() \
                     and query not in status.lower() \
                     and query not in notes.lower():
                continue
            if sf != "All":
                if sf == "Other":
                    if status in STATUS_COLORS: continue
                elif status != sf:
                    continue
            if pt_filt == " Disponible"    and not has_pt:   continue
            if pt_filt == " Non disponible" and has_pt:      continue
            if owned_filt == " YES"         and not is_owned: continue
            if owned_filt == " NO"          and is_owned:     continue

            filtered.append((name, data, has_pt, is_owned))

        if self._sort_col is not None:
            filtered.sort(key=self._sort_key, reverse=(self._sort_asc is False))
        else:
            filtered.sort(key=lambda x: x[0].lower())

        for name, data, has_pt, is_owned in filtered:
            status    = data.get("status", "")
            notes     = data.get("notes",  "")
            pt_txt    = "YES" if has_pt   else "NO"
            owned_txt = "YES" if is_owned else "NO"

            if is_core:
                row_tag = "core_yes" if has_pt else "core_no"
            else:
                row_tag = status if status in STATUS_COLORS else "Other"

            tags = [row_tag] + (["new"] if name in new_names else [])
            self._tree.insert("", "end",
                              values=(name, status, pt_txt, notes, owned_txt),
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

    # ── Settings Window ───────────────────────────────────────────────────────
    def _open_settings(self):
        win = tk.Toplevel(self)
        win.title("Paramètres")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Frame(win, bg=ACCENT, height=3).pack(fill="x")

        pad = tk.Frame(win, bg=BG, padx=24, pady=20)
        pad.pack(fill="both", expand=True)

        tk.Label(pad, text="PARAMÈTRES", bg=BG, fg=ACCENT2,
                 font=("Courier New", 11, "bold")).pack(anchor="w", pady=(0, 16))

        # ── Releases ──────────────────────────────────────────────────────
        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))

        releases_var = tk.BooleanVar(value=self._check_releases)
        rel_row = tk.Frame(pad, bg=BG)
        rel_row.pack(fill="x", pady=(0, 4))
        tk.Checkbutton(rel_row, text="Vérifier les releases GitHub lors du check",
                       variable=releases_var,
                       bg=BG, fg=TEXT, selectcolor=BG3,
                       activebackground=BG, activeforeground=TEXT,
                       font=("Courier New", 9, "bold")).pack(side="left")
        tk.Label(pad,
                 text="Effectue un appel API GitHub par jeu (~400 requêtes). Désactivé par défaut.\n"
                      "Recommandé : activer uniquement avec un token configuré ci-dessous.",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 8),
                 justify="left").pack(anchor="w", pady=(0, 10))

        tk.Label(pad, text="GitHub Personal Access Token",
                 bg=BG, fg=TEXT, font=("Courier New", 9, "bold")).pack(anchor="w")
        tk.Label(pad,
                 text="Nécessaire pour dépasser la limite de 60 req/h de l'API GitHub.\n"
                      "Token requis : scope 'public_repo' (lecture seule suffit).",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 8),
                 justify="left").pack(anchor="w", pady=(2, 6))

        token_var = tk.StringVar(value=self._github_token)
        token_frame = tk.Frame(pad, bg=BG)
        token_frame.pack(fill="x")

        token_entry = tk.Entry(token_frame, textvariable=token_var,
                               bg=BG3, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=("Courier New", 9),
                               width=48, show="•")
        token_entry.pack(side="left", ipady=5, padx=(0, 6))

        # Toggle visibility
        show_var = tk.BooleanVar(value=False)
        def _toggle_show():
            token_entry.config(show="" if show_var.get() else "•")
        tk.Checkbutton(token_frame, text="Afficher", variable=show_var,
                       command=_toggle_show,
                       bg=BG, fg=TEXT_DIM, selectcolor=BG3,
                       activebackground=BG, font=("Courier New", 8)).pack(side="left")

        # Link to create token
        lnk = tk.Label(pad,
                        text="→ Créer un token sur github.com/settings/tokens",
                        bg=BG, fg=ACCENT2, font=("Courier New", 8, "underline"),
                        cursor="hand2")
        lnk.pack(anchor="w", pady=(4, 0))
        lnk.bind("<Button-1>", lambda e: webbrowser.open(
            "https://github.com/settings/tokens/new?description=ArchipelagoTracker&scopes=public_repo"))

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(16, 12))

        # ── Steam ─────────────────────────────────────────────────────────
        tk.Label(pad, text="Steam", bg=BG, fg=TEXT,
                 font=("Courier New", 9, "bold")).pack(anchor="w")
        tk.Label(pad,
                 text="Permet d'afficher la colonne Owned (jeux possédés sur Steam).",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 8),
                 justify="left").pack(anchor="w", pady=(2, 8))

        tk.Label(pad, text="Steam Web API Key :", bg=BG, fg=TEXT_DIM,
                 font=("Courier New", 8)).pack(anchor="w")
        _s = load_settings()
        steam_key_var = tk.StringVar(value=_s.get("steam_api_key", ""))
        steam_key_entry = tk.Entry(pad, textvariable=steam_key_var,
                                   bg=BG3, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=("Courier New", 9),
                                   width=48, show="•")
        steam_key_entry.pack(anchor="w", ipady=5, pady=(2, 2))

        show_sk_var = tk.BooleanVar(value=False)
        def _toggle_sk():
            steam_key_entry.config(show="" if show_sk_var.get() else "•")
        tk.Checkbutton(pad, text="Afficher la clé", variable=show_sk_var,
                       command=_toggle_sk,
                       bg=BG, fg=TEXT_DIM, selectcolor=BG3,
                       activebackground=BG, font=("Courier New", 8)).pack(anchor="w")

        sk_lnk = tk.Label(pad,
                           text="→ Obtenir une clé sur steamcommunity.com/dev/apikey",
                           bg=BG, fg=ACCENT2, font=("Courier New", 8, "underline"),
                           cursor="hand2")
        sk_lnk.pack(anchor="w", pady=(2, 10))
        sk_lnk.bind("<Button-1>", lambda e: webbrowser.open(
            "https://steamcommunity.com/dev/apikey"))

        tk.Label(pad, text="Steam ID(s) — un par ligne (compte unique ou famille) :",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 8)).pack(anchor="w")
        steam_ids_txt = tk.Text(pad, bg=BG3, fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=("Courier New", 9),
                                width=48, height=4)
        steam_ids_txt.insert("1.0", _s.get("steam_ids", ""))
        steam_ids_txt.pack(anchor="w", pady=(2, 4))
        tk.Label(pad,
                 text="Trouver votre Steam ID : steamidfinder.com",
                 bg=BG, fg=TEXT_DIM, font=("Courier New", 8)).pack(anchor="w")

        # ── Steam refresh button ──────────────────────────────────────────
        steam_status_lbl = tk.Label(pad, text="", bg=BG, fg=TEXT_DIM,
                                    font=("Courier New", 8))
        steam_status_lbl.pack(anchor="w", pady=(4, 0))

        def _do_steam_refresh(btn):
            key  = steam_key_var.get().strip()
            ids  = [x.strip() for x in steam_ids_txt.get("1.0", "end").splitlines()
                    if x.strip()]
            if not key or not ids:
                steam_status_lbl.config(
                    text="⚠ Clé API et au moins un Steam ID requis.", fg=YELLOW)
                return
            btn.config(state="disabled", text="🎮  Chargement...")
            steam_status_lbl.config(text="Connexion à Steam...", fg=TEXT_DIM)

            def _thread():
                owned = fetch_steam_owned(key, ids)
                def _done():
                    if owned:
                        self._steam_owned = owned
                        cache = load_cache()
                        cache["_steam_owned"] = list(owned)
                        save_cache(cache)
                        steam_status_lbl.config(
                            text="✓ " + str(len(owned)) + " jeux détectés et sauvegardés.",
                            fg=GREEN)
                        self._refresh_table()
                    else:
                        steam_status_lbl.config(
                            text="✗ Échec — vérifiez la clé et les Steam IDs.",
                            fg=RED)
                    btn.config(state="normal", text="🎮  Actualiser Steam")
                win.after(0, _done)
            threading.Thread(target=_thread, daemon=True).start()

        steam_btn = tk.Button(pad, text="🎮  Actualiser Steam",
                              bg=BG3, fg=TEXT,
                              font=("Courier New", 9, "bold"),
                              relief="flat", padx=12, pady=5, cursor="hand2",
                              activebackground=ACCENT, activeforeground="white")
        steam_btn.config(command=lambda: _do_steam_refresh(steam_btn))
        steam_btn.pack(anchor="w", pady=(6, 0))

        if self._steam_owned:
            steam_status_lbl.config(
                text="Cache actuel : " + str(len(self._steam_owned)) + " jeux.",
                fg=TEXT_DIM)

        tk.Frame(pad, bg=BORDER, height=1).pack(fill="x", pady=(16, 12))

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = tk.Frame(pad, bg=BG)
        btn_row.pack(fill="x")

        def _save():
            self._github_token   = token_var.get().strip()
            self._check_releases = releases_var.get()
            s = load_settings()
            s["github_token"]   = self._github_token
            s["check_releases"] = self._check_releases
            s["steam_api_key"]  = steam_key_var.get().strip()
            s["steam_ids"]      = steam_ids_txt.get("1.0", "end").strip()
            save_settings(s)
            win.destroy()

        tk.Button(btn_row, text="Enregistrer", command=_save,
                  bg=ACCENT, fg="white", font=("Courier New", 9, "bold"),
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  activebackground=ACCENT2, activeforeground="white").pack(side="right")
        tk.Button(btn_row, text="Annuler", command=win.destroy,
                  bg=BG3, fg=TEXT_DIM, font=("Courier New", 9),
                  relief="flat", padx=14, pady=5, cursor="hand2",
                  activebackground=BG3, activeforeground=TEXT).pack(side="right", padx=(0, 8))

    # ── Status bar ────────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_bar.config(text=msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = ArchipelagoTracker()
    app.mainloop()