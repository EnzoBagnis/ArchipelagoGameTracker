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

# ── DATA LOGIC ────────────────────────────────────────────────────────────────
def fetch_tab(tab_name, gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return []
    return list(csv.reader(io.StringIO(r.content.decode("utf-8"))))

def rows_to_dict(rows):
    result = {}
    for row in rows[1:]:
        if len(row) < 2:
            continue
        name   = row[0].strip()
        status = row[1].strip() if len(row) > 1 else ""
        notes  = row[2].strip() if len(row) > 2 else ""
        if not name or name in SKIP_NAMES:
            continue
        result[name] = {"status": status, "notes": notes}
    return result

URL_PATTERN = re.compile(r'https?://\S+')

def extract_urls(text):
    return URL_PATTERN.findall(text)

def fetch_poptracker_games():
    """
    Récupère la liste des jeux avec PopTracker depuis le wiki Archipelago.
    Retourne un set de noms normalisés (lowercase, sans ponctuation).
    """
    try:
        headers = {"User-Agent": "ArchipelagoTracker/1.0"}
        r = requests.get(POPTRACKER_API, timeout=15, headers=headers)
        if r.status_code != 200:
            return set()
        data = r.json()
        members = data.get("query", {}).get("categorymembers", [])
        # Normalise les noms : lowercase, retire les underscores et tirets
        names = set()
        for m in members:
            title = m.get("title", "")
            names.add(_normalize(title))
        return names
    except Exception:
        return set()

def _normalize(name):
    """Normalise un nom de jeu pour la comparaison floue."""
    n = name.lower()
    # Retire préfixes wiki inutiles
    for prefix in ["category:", "game:"]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    # Retire ponctuation et espaces superflus
    n = re.sub(r"[:\-_'\"!.,&()]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n

def match_poptracker(game_name, poptracker_set):
    """Cherche si un jeu a un PopTracker en comparaison floue."""
    norm = _normalize(game_name)
    # Correspondance exacte
    if norm in poptracker_set:
        return True
    # Correspondance partielle (le nom du jeu est contenu dans un nom wiki)
    for pt in poptracker_set:
        if norm in pt or pt in norm:
            if len(norm) > 4 and len(pt) > 4:  # évite les faux positifs courts
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

class ArchipelagoTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Archipelago Tracker")
        self.geometry("1150x740")
        self.minsize(900, 600)
        self.configure(bg=BG)

        # Icône fenêtre
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
        self._poptracker_set = set()   # noms normalisés des jeux avec PopTracker
        self._filter_var     = tk.StringVar()
        self._tab_var        = tk.StringVar(value="Playable Worlds")
        self._status_filter  = tk.StringVar(value="All")
        self._pt_filter      = tk.StringVar(value="All")   # filtre PopTracker
        self._checking       = False

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
                                value=tab, command=self._refresh_table,
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

        # Filtre PopTracker
        tk.Label(fbar, text="  PopTracker:", bg=BG3, fg=TEXT_DIM,
                 font=("Courier New", 9)).pack(side="left", padx=(12, 4))
        ttk.Combobox(fbar, textvariable=self._pt_filter,
                     values=["All", "✅ Disponible", "❌ Non disponible"],
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

        cols = ("game", "status", "poptracker", "notes")
        self._tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings", style="Custom.Treeview")
        self._tree.heading("game",       text="Jeu",        anchor="w")
        self._tree.heading("status",     text="Statut",     anchor="w")
        self._tree.heading("poptracker", text="PopTracker", anchor="w")
        self._tree.heading("notes",      text="Notes",      anchor="w")
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
        self._tree.tag_configure("Other", foreground=TEXT_DIM)
        self._tree.tag_configure("new",   background="#1a2e1a")

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # ── Detail Panel ─────────────────────────────────────────────────────
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")

        detail = tk.Frame(right, bg=BG2, height=160)
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

        self._detail_notes = tk.Label(detail, text="", bg=BG2, fg=TEXT_DIM,
                                      font=("Courier New", 9), anchor="w",
                                      justify="left", wraplength=700, padx=14)
        self._detail_notes.pack(fill="x")

        self._links_frame = tk.Frame(detail, bg=BG2, padx=14, pady=4)
        self._links_frame.pack(fill="x")

    # ── Mouse wheel ───────────────────────────────────────────────────────────
    def _on_mousewheel_changes(self, event):
        self._changes_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # ── Initial Load ──────────────────────────────────────────────────────────
    def _load_initial(self):
        cache = load_cache()
        if cache:
            self._all_games      = cache
            self._poptracker_set = set(cache.get("_poptracker", []))
            self._refresh_table()
            ts = cache.get("_timestamp", "")
            if ts:
                self._last_check_lbl.config(text=f"Dernier check: {ts}")
            total = sum(len(v) for k, v in cache.items()
                        if k not in ("_timestamp", "_poptracker"))
            self._set_status(f"Cache chargé — {total} jeux · {len(self._poptracker_set)} avec PopTracker")
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
        cache    = load_cache()
        new_cache = {"_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        changes  = []

        # ── Google Sheets ──────────────────────────────────────────────────
        for tab_name, gid in TABS.items():
            self._set_status(f"Récupération: {tab_name}...")
            rows = fetch_tab(tab_name, gid)
            if not rows:
                new_cache[tab_name] = cache.get(tab_name, {})
                continue

            current = rows_to_dict(rows)
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
                changes.append(("➕", tab_name, game, data["status"], "Ajouté"))
            for game in removed:
                changes.append(("➖", tab_name, game, "", "Retiré"))
            for game, (before, after) in modified.items():
                changes.append(("🔄", tab_name, game, after, f"{before} → {after}"))

            new_cache[tab_name] = current

        # ── PopTracker Wiki ────────────────────────────────────────────────
        self._set_status("Récupération: PopTracker Wiki...")
        pt_set = fetch_poptracker_games()
        if pt_set:
            self._poptracker_set = pt_set
            new_cache["_poptracker"] = list(pt_set)
        else:
            # Garde l'ancien cache si la requête échoue
            self._poptracker_set = set(cache.get("_poptracker", []))
            new_cache["_poptracker"] = list(self._poptracker_set)

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
        n = len(self._changes)
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

        for icon, tab, game, status, desc in self._changes:
            row = tk.Frame(self._changes_inner, bg=BG2, pady=6, padx=14)
            row.pack(fill="x")
            top_row = tk.Frame(row, bg=BG2)
            top_row.pack(fill="x")
            tk.Label(top_row, text=icon, bg=BG2,
                     font=("Segoe UI Emoji", 11)).pack(side="left")
            tk.Label(top_row, text=f"  {game}", bg=BG2, fg=TEXT,
                     font=("Courier New", 9, "bold"),
                     wraplength=280, justify="left").pack(side="left")
            bot_row = tk.Frame(row, bg=BG2)
            bot_row.pack(fill="x")
            color = STATUS_COLORS.get(status, TEXT_DIM)
            tk.Label(bot_row, text=f"   {tab} — {desc}",
                     bg=BG2, fg=color, font=("Courier New", 8)).pack(side="left")
            tk.Frame(self._changes_inner, bg=BORDER, height=1).pack(fill="x", padx=14)

    # ── Refresh Games Table ───────────────────────────────────────────────────
    def _refresh_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        tab   = self._tab_var.get()
        games = self._all_games.get(tab, {})
        if not isinstance(games, dict):
            return

        query    = self._filter_var.get().lower()
        sf       = self._status_filter.get()
        pt_filt  = self._pt_filter.get()
        new_names = {g for icon, t, g, *_ in self._changes if icon == "➕" and t == tab}

        count = 0
        for name, data in sorted(games.items()):
            if not isinstance(data, dict):
                continue
            status = data.get("status", "")
            notes  = data.get("notes",  "")
            has_pt = match_poptracker(name, self._poptracker_set)
            pt_txt = "✅" if has_pt else "❌"

            # Filtres
            if query and query not in name.lower() \
                     and query not in status.lower() \
                     and query not in notes.lower():
                continue
            if sf != "All":
                if sf == "Other":
                    if status in STATUS_COLORS: continue
                elif status != sf:
                    continue
            if pt_filt == "✅ Disponible"    and not has_pt: continue
            if pt_filt == "❌ Non disponible" and has_pt:    continue

            tag  = status if status in STATUS_COLORS else "Other"
            tags = [tag] + (["new"] if name in new_names else [])

            self._tree.insert("", "end",
                              values=(name, status, pt_txt, notes),
                              tags=tags)
            count += 1

        self._count_lbl.config(text=f"{count} jeux")

    # ── Detail Panel ─────────────────────────────────────────────────────────
    def _on_row_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if not values or len(values) < 4:
            return
        name, status, pt_txt, notes = values[0], values[1], values[2], values[3]

        self._detail_title.config(text=name, fg=TEXT)
        color = STATUS_COLORS.get(status, TEXT_DIM)
        self._detail_status.config(text=f"● {status}", fg=color)

        has_pt = match_poptracker(name, self._poptracker_set)
        if has_pt:
            wiki_url = "https://archipelago.miraheze.org/wiki/" + \
                       name.replace(" ", "_")
            self._detail_pt.config(
                text="🎯 PopTracker: ✅",
                fg=GREEN, cursor="hand2")
            self._detail_pt.bind("<Button-1>",
                lambda e, u=wiki_url: webbrowser.open(u))
        else:
            self._detail_pt.config(text="🎯 PopTracker: ❌", fg=RED, cursor="")
            self._detail_pt.unbind("<Button-1>")

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
            return f"{host}{path}"
        except Exception:
            return url[:50] + "…"

    # ── Status bar ────────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_bar.config(text=msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = ArchipelagoTracker()
    app.mainloop()