import tkinter as tk
from tkinter import ttk, filedialog
import threading
import webbrowser

from config import (
    BG, BG3, ACCENT, ACCENT2, TEXT, TEXT_DIM, BORDER, GREEN, RED, YELLOW
)
from cache import load_settings, save_settings, load_cache, save_cache
from lang.l18n import t
from data import fetch_steam_owned, fetch_itch_owned, load_playnite_library


def open_settings(app):
    """Open the ⚙ settings Toplevel window."""
    win = tk.Toplevel(app)
    win.title(t("settings_title"))
    win.configure(bg=BG)
    # Resizable, with a reasonable default size
    win.resizable(True, True)
    win.minsize(520, 400)
    win.grab_set()

    tk.Frame(win, bg=ACCENT, height=3).pack(fill="x")

    # Scrollable container
    outer = tk.Frame(win, bg=BG)
    outer.pack(fill="both", expand=True)

    canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = tk.Frame(canvas, bg=BG)

    inner.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    _inner_win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    # Keep inner frame width in sync with canvas so labels can wrap properly
    def _on_canvas_resize(event):
        canvas.itemconfig(_inner_win, width=event.width)
    canvas.bind("<Configure>", _on_canvas_resize)

    def _scroll(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind("<Enter>", lambda e: win.bind("<MouseWheel>", _scroll))
    canvas.bind("<Leave>", lambda e: win.unbind("<MouseWheel>"))
    inner.bind("<Enter>",  lambda e: win.bind("<MouseWheel>", _scroll))
    inner.bind("<Leave>",  lambda e: win.unbind("<MouseWheel>"))

    pad = tk.Frame(inner, bg=BG, padx=24, pady=20)
    pad.pack(fill="both", expand=True)

    tk.Label(pad, text=t("settings_heading"), bg=BG, fg=ACCENT2,
             font=("Courier New", 11, "bold")).pack(anchor="w", pady=(0, 16))

    # ── Wrap helper: labels auto-wrap when window is resized ──────────────
    def _wrapping_label(parent, text, **kw):
        """Create a Label that wraps automatically when the window is resized."""
        lbl = tk.Label(parent, text=text, bg=BG, fg=TEXT_DIM,
                       font=("Courier New", 8), justify="left",
                       anchor="w", **kw)
        lbl.pack(anchor="w", pady=(0, 6), fill="x")

        def _update_wrap(event):
            # event.width = canvas width; subtract padx*2 + scrollbar margin
            lbl.config(wraplength=max(200, event.width - 64))

        canvas.bind("<Configure>", _update_wrap, add="+")
        return lbl

    # ── GitHub releases ────────────────────────────────────────────────────
    _section_sep(pad)
    releases_var = tk.BooleanVar(value=app._check_releases)
    rel_row = tk.Frame(pad, bg=BG)
    rel_row.pack(fill="x", pady=(0, 4))
    tk.Checkbutton(rel_row, text=t("settings_github_check_label"),
                   variable=releases_var,
                   bg=BG, fg=TEXT, selectcolor=BG3,
                   activebackground=BG, activeforeground=TEXT,
                   font=("Courier New", 9, "bold")).pack(side="left")
    _wrapping_label(pad, t("settings_github_check_hint"))

    tk.Label(pad, text=t("settings_github_token_label"),
             bg=BG, fg=TEXT, font=("Courier New", 9, "bold")).pack(anchor="w")
    _wrapping_label(pad, t("settings_github_token_hint"))

    token_var = tk.StringVar(value=app._github_token)
    token_frame = tk.Frame(pad, bg=BG)
    token_frame.pack(fill="x")
    token_entry = tk.Entry(token_frame, textvariable=token_var,
                           bg=BG3, fg=TEXT, insertbackground=TEXT,
                           relief="flat", font=("Courier New", 9),
                           width=48, show="•")
    token_entry.pack(side="left", ipady=5, padx=(0, 6))
    show_var = tk.BooleanVar(value=False)
    tk.Checkbutton(token_frame, text=t("settings_github_show"), variable=show_var,
                   command=lambda: token_entry.config(
                       show="" if show_var.get() else "•"),
                   bg=BG, fg=TEXT_DIM, selectcolor=BG3,
                   activebackground=BG, font=("Courier New", 8)).pack(side="left")

    lnk = tk.Label(pad, text=t("settings_github_token_link"),
                   bg=BG, fg=ACCENT2, font=("Courier New", 8, "underline"),
                   cursor="hand2")
    lnk.pack(anchor="w", pady=(4, 0))
    lnk.bind("<Button-1>", lambda e: webbrowser.open(
        "https://github.com/settings/tokens/new"
        "?description=GameSupportTracker&scopes=public_repo"))

    # ── Steam ──────────────────────────────────────────────────────────────
    _section_sep(pad)
    tk.Label(pad, text=t("settings_steam_heading"), bg=BG, fg=TEXT,
             font=("Courier New", 9, "bold")).pack(anchor="w")
    _wrapping_label(pad, t("settings_steam_hint"))

    _s = load_settings()

    tk.Label(pad, text=t("settings_steam_key_label"), bg=BG, fg=TEXT_DIM,
             font=("Courier New", 8)).pack(anchor="w")
    steam_key_var = tk.StringVar(value=_s.get("steam_api_key", ""))
    steam_key_entry = tk.Entry(pad, textvariable=steam_key_var,
                               bg=BG3, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=("Courier New", 9),
                               width=48, show="•")
    steam_key_entry.pack(anchor="w", ipady=5, pady=(2, 2))
    show_sk = tk.BooleanVar(value=False)
    tk.Checkbutton(pad, text=t("settings_steam_key_show"), variable=show_sk,
                   command=lambda: steam_key_entry.config(
                       show="" if show_sk.get() else "•"),
                   bg=BG, fg=TEXT_DIM, selectcolor=BG3,
                   activebackground=BG, font=("Courier New", 8)).pack(anchor="w")

    sk_lnk = tk.Label(pad,
                      text=t("settings_steam_key_link"),
                      bg=BG, fg=ACCENT2, font=("Courier New", 8, "underline"),
                      cursor="hand2")
    sk_lnk.pack(anchor="w", pady=(2, 10))
    sk_lnk.bind("<Button-1>", lambda e: webbrowser.open(
        "https://steamcommunity.com/dev/apikey"))

    tk.Label(pad, text=t("settings_steam_ids_label"),
             bg=BG, fg=TEXT_DIM, font=("Courier New", 8)).pack(anchor="w")

    # Steam IDs text area — show full content (no fixed height cap)
    steam_ids_content = _s.get("steam_ids", "")
    line_count = max(4, steam_ids_content.count("\n") + 2)
    steam_ids_txt = tk.Text(pad, bg=BG3, fg=TEXT, insertbackground=TEXT,
                            relief="flat", font=("Courier New", 9),
                            width=48, height=line_count)
    steam_ids_txt.insert("1.0", steam_ids_content)
    steam_ids_txt.pack(anchor="w", pady=(2, 4), fill="x")

    _wrapping_label(pad, t("settings_steam_ids_hint"))

    steam_status_lbl = tk.Label(pad, text="", bg=BG, fg=TEXT_DIM,
                                font=("Courier New", 8))
    steam_status_lbl.pack(anchor="w", pady=(4, 0))

    if app._steam_owned:
        steam_status_lbl.config(
            text=t("settings_steam_cache", n=_s.get("steam_game_count", len(app._steam_owned))),
            fg=TEXT_DIM)

    def _do_steam_refresh(btn):
        key = steam_key_var.get().strip()
        ids = [x.strip() for x in steam_ids_txt.get("1.0", "end").splitlines()
               if x.strip()]
        if not key or not ids:
            steam_status_lbl.config(
                text=t("settings_steam_missing"), fg=YELLOW)
            return
        btn.config(state="disabled", text=t("settings_steam_loading"))
        steam_status_lbl.config(text=t("settings_steam_connecting"), fg=TEXT_DIM)

        def _thread():
            owned_variants, game_count = fetch_steam_owned(key, ids)
            def _done():
                if owned_variants:
                    app._steam_owned = owned_variants
                    c = load_cache()
                    c["_steam_owned"] = list(owned_variants)
                    save_cache(c)
                    s = load_settings()
                    s["steam_game_count"] = game_count
                    save_settings(s)
                    steam_status_lbl.config(
                        text=t("settings_steam_success", n=game_count),
                        fg=GREEN)
                    app._refresh_table()
                else:
                    steam_status_lbl.config(
                        text=t("settings_steam_error"),
                        fg=RED)
                btn.config(state="normal", text=t("settings_steam_btn"))
            win.after(0, _done)
        threading.Thread(target=_thread, daemon=True).start()

    steam_btn = tk.Button(pad, text=t("settings_steam_btn"),
                          bg=BG3, fg=TEXT, font=("Courier New", 9, "bold"),
                          relief="flat", padx=12, pady=5, cursor="hand2",
                          activebackground=ACCENT, activeforeground="white")
    steam_btn.config(command=lambda: _do_steam_refresh(steam_btn))
    steam_btn.pack(anchor="w", pady=(6, 0))

    # ── Itch.io ────────────────────────────────────────────────────────────
    _section_sep(pad)
    tk.Label(pad, text=t("settings_itch_heading"), bg=BG, fg=TEXT,
             font=("Courier New", 9, "bold")).pack(anchor="w")
    _wrapping_label(pad, t("settings_itch_hint"))

    tk.Label(pad, text=t("settings_itch_token_label"), bg=BG, fg=TEXT_DIM,
             font=("Courier New", 8)).pack(anchor="w")
    _wrapping_label(pad, t("settings_itch_token_hint"))

    itch_token_var = tk.StringVar(value=_s.get("itch_token", ""))
    itch_token_frame = tk.Frame(pad, bg=BG)
    itch_token_frame.pack(fill="x")
    itch_token_entry = tk.Entry(itch_token_frame, textvariable=itch_token_var,
                                bg=BG3, fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=("Courier New", 9),
                                width=48, show="•")
    itch_token_entry.pack(side="left", ipady=5, padx=(0, 6))
    show_itch = tk.BooleanVar(value=False)
    tk.Checkbutton(itch_token_frame, text=t("settings_itch_token_show"),
                   variable=show_itch,
                   command=lambda: itch_token_entry.config(
                       show="" if show_itch.get() else "•"),
                   bg=BG, fg=TEXT_DIM, selectcolor=BG3,
                   activebackground=BG, font=("Courier New", 8)).pack(side="left")

    itch_lnk = tk.Label(pad, text=t("settings_itch_token_link"),
                        bg=BG, fg=ACCENT2, font=("Courier New", 8, "underline"),
                        cursor="hand2")
    itch_lnk.pack(anchor="w", pady=(4, 0))
    itch_lnk.bind("<Button-1>", lambda e: webbrowser.open(
        "https://itch.io/docs/api/serverside#authentication/oauth2"))

    itch_status_lbl = tk.Label(pad, text="", bg=BG, fg=TEXT_DIM,
                               font=("Courier New", 8))
    itch_status_lbl.pack(anchor="w", pady=(4, 0))

    if app._itch_owned:
        itch_status_lbl.config(
            text=t("settings_itch_cache", n=_s.get("itch_game_count", len(app._itch_owned))),
            fg=TEXT_DIM)

    def _do_itch_refresh(btn):
        token = itch_token_var.get().strip()
        if not token:
            itch_status_lbl.config(text=t("settings_itch_missing"), fg=YELLOW)
            return
        btn.config(state="disabled", text=t("settings_itch_loading"))
        itch_status_lbl.config(text=t("settings_itch_connecting"), fg=TEXT_DIM)

        def _thread():
            owned_variants, game_count = fetch_itch_owned(token)
            def _done():
                if owned_variants is not None:
                    app._itch_owned = owned_variants
                    c = load_cache()
                    c["_itch_owned"] = list(owned_variants)
                    save_cache(c)
                    s = load_settings()
                    s["itch_token"]      = token
                    s["itch_game_count"] = game_count
                    save_settings(s)
                    itch_status_lbl.config(
                        text=t("settings_itch_success", n=game_count), fg=GREEN)
                    app._refresh_table()
                else:
                    itch_status_lbl.config(
                        text=t("settings_itch_error"), fg=RED)
                btn.config(state="normal", text=t("settings_itch_btn"))
            win.after(0, _done)
        threading.Thread(target=_thread, daemon=True).start()

    itch_btn = tk.Button(pad, text=t("settings_itch_btn"),
                         bg=BG3, fg=TEXT, font=("Courier New", 9, "bold"),
                         relief="flat", padx=12, pady=5, cursor="hand2",
                         activebackground=ACCENT, activeforeground="white")
    itch_btn.config(command=lambda: _do_itch_refresh(itch_btn))
    itch_btn.pack(anchor="w", pady=(6, 0))

    # ── Playnite ───────────────────────────────────────────────────────────
    _section_sep(pad)
    tk.Label(pad, text=t("settings_playnite_heading"), bg=BG, fg=TEXT,
             font=("Courier New", 9, "bold")).pack(anchor="w")
    _wrapping_label(pad, t("settings_playnite_hint"))
    _wrapping_label(pad, t("settings_playnite_hint2"))

    tk.Label(pad, text=t("settings_playnite_path_label"), bg=BG, fg=TEXT_DIM,
             font=("Courier New", 8)).pack(anchor="w")

    playnite_path_var = tk.StringVar(value=_s.get("playnite_path", ""))
    playnite_path_frame = tk.Frame(pad, bg=BG)
    playnite_path_frame.pack(fill="x", pady=(2, 0))
    playnite_path_entry = tk.Entry(playnite_path_frame, textvariable=playnite_path_var,
                                   bg=BG3, fg=TEXT, insertbackground=TEXT,
                                   relief="flat", font=("Courier New", 9), width=42)
    playnite_path_entry.pack(side="left", ipady=5, padx=(0, 6))

    def _browse_playnite():
        path = filedialog.askopenfilename(
            title="Select Playnite library export",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            parent=win)
        if path:
            playnite_path_var.set(path)

    tk.Button(playnite_path_frame, text=t("settings_playnite_browse"),
              bg=BG3, fg=TEXT, font=("Courier New", 8),
              relief="flat", padx=8, pady=4, cursor="hand2",
              activebackground=ACCENT, activeforeground="white",
              command=_browse_playnite).pack(side="left")

    playnite_status_lbl = tk.Label(pad, text="", bg=BG, fg=TEXT_DIM,
                                   font=("Courier New", 8))
    playnite_status_lbl.pack(anchor="w", pady=(4, 0))

    if app._playnite_owned:
        playnite_status_lbl.config(
            text=t("settings_playnite_cache",
                   n=_s.get("playnite_game_count", len(app._playnite_owned))),
            fg=TEXT_DIM)

    def _do_playnite_import(btn):
        path = playnite_path_var.get().strip()
        if not path:
            playnite_status_lbl.config(
                text=t("settings_playnite_missing"), fg=YELLOW)
            return
        btn.config(state="disabled", text=t("settings_playnite_loading"))

        def _thread():
            owned_variants, game_count = load_playnite_library(path)
            def _done():
                if owned_variants:
                    app._playnite_owned = owned_variants
                    c = load_cache()
                    c["_playnite_owned"] = list(owned_variants)
                    save_cache(c)
                    s = load_settings()
                    s["playnite_path"]       = path
                    s["playnite_game_count"] = game_count
                    save_settings(s)
                    playnite_status_lbl.config(
                        text=t("settings_playnite_success", n=game_count),
                        fg=GREEN)
                    app._refresh_table()
                else:
                    playnite_status_lbl.config(
                        text=t("settings_playnite_error"), fg=RED)
                btn.config(state="normal", text=t("settings_playnite_btn"))
            win.after(0, _done)
        threading.Thread(target=_thread, daemon=True).start()

    playnite_btn = tk.Button(pad, text=t("settings_playnite_btn"),
                             bg=BG3, fg=TEXT, font=("Courier New", 9, "bold"),
                             relief="flat", padx=12, pady=5, cursor="hand2",
                             activebackground=ACCENT, activeforeground="white")
    playnite_btn.config(command=lambda: _do_playnite_import(playnite_btn))
    playnite_btn.pack(anchor="w", pady=(6, 0))

    # ── Language ───────────────────────────────────────────────────────────
    _section_sep(pad)
    tk.Label(pad, text=t("settings_lang_heading"), bg=BG, fg=TEXT,
             font=("Courier New", 9, "bold")).pack(anchor="w")
    tk.Label(pad, text=t("settings_lang_label"), bg=BG, fg=TEXT_DIM,
             font=("Courier New", 8)).pack(anchor="w", pady=(2, 4))
    from lang.l18n import available_langs, current_lang
    langs = available_langs()
    lang_codes = list(langs.keys())
    lang_names = [langs[c] for c in lang_codes]
    cur = current_lang()
    lang_var = tk.StringVar(value=langs.get(cur, cur))
    lang_row = tk.Frame(pad, bg=BG)
    lang_row.pack(anchor="w")
    lang_combo = ttk.Combobox(lang_row, textvariable=lang_var,
                              values=lang_names, state="readonly",
                              font=("Courier New", 9), width=28)
    lang_combo.pack(side="left")

    def _apply_lang():
        sel_name = lang_var.get()
        for code, name in langs.items():
            if name == sel_name:
                s = load_settings()
                s["lang"] = code
                save_settings(s)
                try:
                    from lang.l18n import set_lang
                    set_lang(code)
                except Exception:
                    pass
                try:
                    confirm_lbl.config(text=t("settings_lang_saved"))
                    win.after(2000, lambda: confirm_lbl.config(text=""))
                except Exception:
                    pass
                break

    apply_btn = tk.Button(lang_row, text=t("settings_lang_apply"),
                          bg=ACCENT, fg="white", font=("Courier New", 8, "bold"),
                          relief="flat", padx=8, pady=2, cursor="hand2",
                          activebackground=ACCENT2, activeforeground="white",
                          command=_apply_lang)
    apply_btn.pack(side="left", padx=(8, 0))

    confirm_lbl = tk.Label(pad, text="", bg=BG, fg=GREEN,
                           font=("Courier New", 8))
    confirm_lbl.pack(anchor="w", pady=(2, 0))

    tk.Label(pad, text=t("settings_lang_note"), bg=BG, fg=TEXT_DIM,
             font=("Courier New", 8)).pack(anchor="w", pady=(2, 0))

    # ── Save / Cancel (fixed footer) ───────────────────────────────────────
    def _save():
        app._github_token   = token_var.get().strip()
        app._check_releases = releases_var.get()
        s = load_settings()
        s["github_token"]    = app._github_token
        s["check_releases"]  = app._check_releases
        s["steam_api_key"]   = steam_key_var.get().strip()
        s["steam_ids"]       = steam_ids_txt.get("1.0", "end").strip()
        s["itch_token"]      = itch_token_var.get().strip()
        s["playnite_path"]   = playnite_path_var.get().strip()
        sel_name = lang_var.get()
        for code, name in langs.items():
            if name == sel_name:
                s["lang"] = code
                try:
                    from lang.l18n import set_lang
                    set_lang(code)
                except Exception:
                    pass
                break
        save_settings(s)
        win.destroy()

    footer = tk.Frame(win, bg=BG, pady=8)
    footer.pack(fill="x", side="bottom")
    tk.Frame(footer, bg=BORDER, height=1).pack(fill="x", side="top")
    btn_row = tk.Frame(footer, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(8, 4))

    tk.Button(btn_row, text=t("settings_save"), command=_save,
              bg=ACCENT, fg="white", font=("Courier New", 9, "bold"),
              relief="flat", padx=14, pady=5, cursor="hand2",
              activebackground=ACCENT2, activeforeground="white").pack(side="right")
    tk.Button(btn_row, text=t("settings_cancel"), command=win.destroy,
              bg=BG3, fg=TEXT_DIM, font=("Courier New", 9),
              relief="flat", padx=14, pady=5, cursor="hand2",
              activebackground=BG3, activeforeground=TEXT).pack(side="right", padx=(0, 8))

    # ── Size the window ────────────────────────────────────────────────────
    win.update_idletasks()
    content_h = inner.winfo_reqheight() + 80   # footer + padding
    screen_h  = app.winfo_screenheight()
    default_h = min(content_h, int(screen_h * 0.75))
    win.geometry(f"630x{default_h}")


def _section_sep(parent):
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(0, 12))