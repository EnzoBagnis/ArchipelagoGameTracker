import tkinter as tk
from tkinter import ttk
import sys
import os
import threading
from datetime import datetime

from config import (
    TABS, BG, BG2, BG3, ACCENT, ACCENT2, TEXT, TEXT_DIM, BORDER, SORT_ICONS
)
from cache import load_cache, save_cache, load_settings
from data import (
    fetch_tab, rows_to_dict, extract_github_repo,
    fetch_github_release, fetch_poptracker_games
)
from ui.changes import build_changes_panel, refresh_changes
from ui.table   import build_filter_bar, build_tree, apply_columns, \
                       update_heading_icons, refresh_table
from ui.detail  import build_detail_panel, update_detail
from ui.settings import open_settings
from lang.l18n import t


class ArchipelagoTracker(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(t("app_title"))
        self.geometry("1150x740")
        self.minsize(900, 600)
        self.configure(bg=BG)

        try:
            if getattr(sys, "frozen", False):
                icon_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                icon_path = os.path.join(os.path.dirname(__file__), "logo.ico")
            self.iconbitmap(icon_path)
        except Exception:
            pass

        # ── State ─────────────────────────────────────────────────────────
        self._changes        = []
        self._all_games      = {}
        self._poptracker_set = set()
        self._releases       = {}
        self._steam_owned    = set()

        _s = load_settings()
        self._github_token   = _s.get("github_token", "")
        self._check_releases = _s.get("check_releases", False)

        self._filter_var    = tk.StringVar()
        self._tab_var       = tk.StringVar(value="Playable Worlds")
        self._status_filter = tk.StringVar(value="All")
        self._pt_filter     = tk.StringVar(value="All")
        self._owned_filter  = tk.StringVar(value="All")
        self._checking      = False

        self._sort_col = None
        self._sort_asc = None

        # Mousewheel routing
        self._mw_target = None

        self._build_ui()
        self.after(200, self._load_initial)

    # ── Mousewheel routing ─────────────────────────────────────────────────────
    def _on_mousewheel(self, event):
        if self._mw_target:
            self._mw_target(event)

    def _register_scroll(self, widget, callback):
        widget.bind("<Enter>", lambda e, cb=callback: setattr(self, "_mw_target", cb))
        widget.bind("<Leave>", lambda e, cb=callback: (
            setattr(self, "_mw_target", None)
            if self._mw_target is cb else None))

    def _scroll_changes(self, event):
        self._changes_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _scroll_tree(self, event):
        self._tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── Build UI ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        self.bind_all("<MouseWheel>", self._on_mousewheel)

        # Header bar
        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

        top = tk.Frame(self, bg=BG, pady=16, padx=20)
        top.pack(fill="x")
        tk.Label(top, text=t("app_title"),
                 bg=BG, fg=TEXT, font=("Courier New", 18, "bold")).pack(side="left")

        self._status_bar = tk.Label(top, text=t("status_ready"), bg=BG, fg=TEXT_DIM,
                                    font=("Courier New", 10))
        self._status_bar.pack(side="right", padx=10)

        self._check_btn = tk.Button(
            top, text=t("btn_check"),
            command=self._start_check,
            bg=ACCENT, fg="white", font=("Courier New", 10, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground=ACCENT2, activeforeground="white")
        self._check_btn.pack(side="right")

        tk.Button(top, text="⚙", command=lambda: open_settings(self),
                  bg=BG, fg=TEXT_DIM, font=("Courier New", 12), relief="flat",
                  padx=8, pady=4, cursor="hand2",
                  activebackground=BG3, activeforeground=TEXT
                  ).pack(side="right", padx=(0, 4))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Paned window
        self._paned = tk.PanedWindow(self, orient="horizontal",
                                     bg=BG, sashwidth=5,
                                     sashrelief="flat", sashpad=0, handlesize=0)
        self._paned.pack(fill="both", expand=True)

        # Left panel (changes)
        left = tk.Frame(self._paned, bg=BG2, width=300)
        left.pack_propagate(False)
        self._left_panel = left
        self._paned.add(left, minsize=0, width=300)

        (self._changes_canvas,
         self._changes_inner,
         self._last_check_lbl,
         self._toggle_left_btn) = build_changes_panel(left, self)

        self._register_scroll(self._changes_canvas, self._scroll_changes)
        self._register_scroll(self._changes_inner,  self._scroll_changes)

        # Right panel (table)
        right = tk.Frame(self._paned, bg=BG)
        self._right_panel = right
        self._paned.add(right, minsize=400)

        self._count_lbl = build_filter_bar(right, self)
        self._tree      = build_tree(right, self)
        self._register_scroll(self._tree, self._scroll_tree)

        self._detail_widgets = build_detail_panel(right)

        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

    # ── Tab / sort ─────────────────────────────────────────────────────────────
    def _on_tab_change(self):
        self._sort_col = None
        self._sort_asc = None
        update_heading_icons(self._tree, self._tab_var.get(),
                             self._sort_col, self._sort_asc)
        apply_columns(self._tree, self._tab_var.get(),
                      self._sort_col, self._sort_asc)
        self._refresh_table()

    def _on_sort_click(self, col):
        if col == "status" and self._tab_var.get() == "Core Verified":
            return
        if self._sort_col != col:
            self._sort_col, self._sort_asc = col, True
        else:
            if self._sort_asc is True:
                self._sort_asc = False
            elif self._sort_asc is False:
                self._sort_col = self._sort_asc = None
            else:
                self._sort_col, self._sort_asc = col, True
        update_heading_icons(self._tree, self._tab_var.get(),
                             self._sort_col, self._sort_asc)
        self._refresh_table()

    # ── Toggle left panel ──────────────────────────────────────────────────────
    def _toggle_left_panel(self):
        panes = self._paned.panes()
        if str(self._left_panel) in panes:
            self._left_panel_width = self._paned.sash_coord(0)[0]
            self._paned.forget(self._left_panel)
            self._toggle_left_btn.config(text="▶")
            self._show_left_btn.pack(side="left", padx=(0, 8))
        else:
            self._paned.add(self._left_panel, minsize=0,
                            width=getattr(self, "_left_panel_width", 300),
                            before=self._right_panel)
            self._toggle_left_btn.config(text="◀")
            self._show_left_btn.pack_forget()

    # ── Refresh helpers ────────────────────────────────────────────────────────
    def _refresh_table(self):
        apply_columns(self._tree, self._tab_var.get(),
                      self._sort_col, self._sort_asc)
        refresh_table(self._tree, self)

    def _refresh_changes(self):
        refresh_changes(self._changes_inner, self._changes,
                        self._register_scroll, self._scroll_changes)

    # ── Row select ─────────────────────────────────────────────────────────────
    def _on_row_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], "values")
        if not values or len(values) < 4:
            return
        name, status, _pt, notes = values[0], values[1], values[2], values[3]
        update_detail(self._detail_widgets, name, status, notes,
                      self._tab_var.get(), self._releases, self._poptracker_set)

    # ── Initial load ───────────────────────────────────────────────────────────
    def _load_initial(self):
        cache = load_cache()
        apply_columns(self._tree, self._tab_var.get(),
                      self._sort_col, self._sort_asc)
        if cache:
            self._all_games      = cache
            self._poptracker_set = set(cache.get("_poptracker", []))
            self._releases       = cache.get("_releases", {})
            #self._steam_owned    = set(cache.get("_steam_owned", []))
            self._steam_owned    = set(cache.get("_steam_owned", []))
            self._refresh_table()
            ts = cache.get("_timestamp", "")
            if ts:
                self._last_check_lbl.config(text=t("last_check_label", ts=ts))
            total = sum(len(v) for k, v in cache.items()
                        if k not in ("_timestamp", "_poptracker",
                                     "_releases", "_steam_owned"))
            self._set_status(t("status_cache_loaded", total=total, pt=len(self._poptracker_set)))
        else:
            self._set_status(t("status_no_cache"))

    # ── Check ──────────────────────────────────────────────────────────────────
    def _start_check(self):
        if self._checking:
            return
        self._checking = True
        self._check_btn.config(state="disabled", text=t("btn_checking"))
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        cache        = load_cache()
        new_cache    = {"_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
        changes      = []
        old_releases = cache.get("_releases", {})
        new_releases = {}
        rate_limited = False

        for tab_name, gid in TABS.items():
            self._set_status(t("status_fetching_tab", tab=tab_name))
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
            modified = {
                k: (old[k].get("status", "?"), current[k]["status"])
                for k in current
                if k in old and isinstance(old[k], dict)
                and old[k].get("status") != current[k]["status"]
            }

            for game, data in added.items():
                changes.append(("➕", tab_name, game, data["status"], t("changes_added"), ""))
            for game in removed:
                changes.append(("➖", tab_name, game, "", t("changes_removed"), ""))
            for game, (before, after) in modified.items():
                changes.append(("🔄", tab_name, game, after,
                                 t("change_status_update", before=before, after=after), ""))

            new_cache[tab_name] = current

            # GitHub releases
            old_tab_rels = old_releases.get(tab_name, {})
            new_tab_rels = {}
            if tab_name != "Core Verified" and not rate_limited \
                    and self._check_releases:
                total = len(current)
                for idx, (game_name, game_data) in enumerate(current.items()):
                    self._set_status(
                        t("status_fetching_releases", tab=tab_name, idx=idx+1, total=total, game=game_name))
                    repo = extract_github_repo(
                        game_data.get("notes", ""),
                        game_data.get("apworld", ""))
                    if not repo:
                        if game_name in old_tab_rels:
                            new_tab_rels[game_name] = old_tab_rels[game_name]
                        continue
                    owner, repo_name = repo
                    release = fetch_github_release(
                        owner, repo_name, self._github_token)
                    if release == "rate_limited":
                        rate_limited = True
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
                        if old_tag:
                            desc = t("change_release_update", old=old_tag, new=new_tag)
                        else:
                            desc = t("change_release_new", tag=new_tag)
                        changes.append((
                            "🏷️", tab_name, game_name, "",
                            desc, release.get("url", ""),
                        ))
            else:
                new_tab_rels = dict(old_tab_rels)

            new_releases[tab_name] = new_tab_rels

        self._set_status("Récupération: PopTracker Wiki...")
        pt_set = fetch_poptracker_games()
        if pt_set:
            self._poptracker_set     = pt_set
            new_cache["_poptracker"] = list(pt_set)
        else:
            self._poptracker_set     = set(cache.get("_poptracker", []))
            new_cache["_poptracker"] = list(self._poptracker_set)

        # Steam — refresh only via ⚙, keep cache
        self._steam_owned         = set(cache.get("_steam_owned", []))
        new_cache["_steam_owned"] = list(self._steam_owned)

        new_cache["_releases"] = new_releases
        self._releases         = new_releases
        save_cache(new_cache)
        self._all_games = new_cache
        self._changes   = changes
        self.after(0, lambda: self._on_check_done(rate_limited))

    def _on_check_done(self, rate_limited=False):
        self._checking = False
        self._check_btn.config(state="normal", text=t("btn_check"))
        self._last_check_lbl.config(
            text=t("last_check_label", ts=self._all_games.get('_timestamp', '')))
        self._refresh_table()
        self._refresh_changes()
        n  = len(self._changes)
        pt = len(self._poptracker_set)
        if rate_limited:
            self._set_status(t("status_rate_limited"))
        else:
            self._set_status(t("status_done", n=n, pt=pt))

    # ── Status bar ─────────────────────────────────────────────────────────────
    def _set_status(self, msg):
        self._status_bar.config(text=msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = ArchipelagoTracker()
    app.mainloop()