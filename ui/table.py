import tkinter as tk
from tkinter import ttk

from config import (
    TABS, STATUS_COLORS, STATUS_ORDER, SORT_ICONS,
    BG, BG3, ACCENT, ACCENT2, TEXT, TEXT_DIM, BORDER, GREEN, RED
)
from data import match_poptracker, is_owned_on_steam
from lang.l18n import t


def build_filter_bar(parent, app):
    """Build the two-row filter bar. Returns the count label."""
    fbar = tk.Frame(parent, bg=BG3, pady=6, padx=14)
    fbar.pack(fill="x")

    # Row 1 — tabs + search + count
    r1 = tk.Frame(fbar, bg=BG3)
    r1.pack(fill="x")

    app._show_left_btn = tk.Button(
        r1, text=t("btn_show_changes"), bg=BG3, fg=TEXT_DIM,
        font=("Courier New", 8), relief="flat", cursor="hand2",
        padx=6, pady=2, activebackground="#161b22", activeforeground=TEXT,
        command=app._toggle_left_panel)
    app._show_left_btn.pack(side="left", padx=(0, 8))
    app._show_left_btn.pack_forget()

    for tab in TABS.keys():
        rb = tk.Radiobutton(r1, text=tab, variable=app._tab_var,
                            value=tab, command=app._on_tab_change,
                            bg=BG3, fg=TEXT, selectcolor=BG3,
                            activebackground=BG3, activeforeground=ACCENT2,
                            font=("Courier New", 9, "bold"),
                            indicatoron=False, relief="flat",
                            padx=10, pady=4, cursor="hand2")
        rb.pack(side="left", padx=(0, 4))

    tk.Label(r1, text="🔍", bg=BG3, fg=TEXT_DIM,
             font=("Courier New", 11)).pack(side="left", padx=(16, 4))
    tk.Entry(r1, textvariable=app._filter_var,
             bg=BG, fg=TEXT, insertbackground=TEXT,
             relief="flat", font=("Courier New", 10), width=22
             ).pack(side="left", ipady=4)
    app._filter_var.trace_add("write", lambda *a: app._refresh_table())

    count_lbl = tk.Label(r1, text="", bg=BG3, fg=TEXT_DIM,
                         font=("Courier New", 9))
    count_lbl.pack(side="right", padx=8)

    # Row 2 — dropdowns
    r2 = tk.Frame(fbar, bg=BG3)
    r2.pack(fill="x", pady=(4, 0))

    tk.Label(r2, text=t("filter_status"), bg=BG3, fg=TEXT_DIM,
             font=("Courier New", 9)).pack(side="left", padx=(0, 4))
    ttk.Combobox(r2, textvariable=app._status_filter,
                 values=[t("filter_all")] + list(STATUS_COLORS.keys()) + ["Other"],
                 state="readonly", width=13,
                 font=("Courier New", 9)).pack(side="left")
    app._status_filter.trace_add("write", lambda *a: app._refresh_table())

    tk.Label(r2, text=t("filter_pt"), bg=BG3, fg=TEXT_DIM,
             font=("Courier New", 9)).pack(side="left", padx=(12, 4))
    ttk.Combobox(r2, textvariable=app._pt_filter,
                 values=[t("filter_all"), t("filter_pt_yes"), t("filter_pt_no")],
                 state="readonly", width=16,
                 font=("Courier New", 9)).pack(side="left")
    app._pt_filter.trace_add("write", lambda *a: app._refresh_table())

    tk.Label(r2, text=t("filter_owned"), bg=BG3, fg=TEXT_DIM,
             font=("Courier New", 9)).pack(side="left", padx=(12, 4))
    ttk.Combobox(r2, textvariable=app._owned_filter,
                 values=[t("filter_all"), t("filter_owned_yes"), t("filter_owned_no")],
                 state="readonly", width=8,
                 font=("Courier New", 9)).pack(side="left")
    app._owned_filter.trace_add("write", lambda *a: app._refresh_table())

    return count_lbl


def build_tree(parent, app):
    """Build the Treeview with scrollbar. Returns the tree widget."""
    table_frame = tk.Frame(parent, bg=BORDER)
    table_frame.pack(fill="both", expand=True)

    tk.Frame(table_frame, bg=BORDER, height=1).pack(fill="x", side="top")

    inner = tk.Frame(table_frame, bg=BG)
    inner.pack(fill="both", expand=True)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Custom.Treeview",
                    background=BG, foreground=TEXT,
                    rowheight=31, fieldbackground=BG,
                    borderwidth=0, font=("Courier New", 9), relief="flat")
    style.configure("Custom.Treeview.Heading",
                    background=BG3, foreground=ACCENT2,
                    font=("Courier New", 9, "bold"), relief="flat",
                    borderwidth=0, padding=(6, 6))
    style.map("Custom.Treeview",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])
    style.map("Custom.Treeview.Heading",
              background=[("active", ACCENT)],
              foreground=[("active", "white")])

    cols = ("game", "status", "poptracker", "notes", "owned")
    tree = ttk.Treeview(inner, columns=cols, show="headings",
                        style="Custom.Treeview")

    tree.heading("game",       text=t("col_game") + SORT_ICONS[None], anchor="w",
                 command=lambda: app._on_sort_click("game"))
    tree.heading("status",     text=t("col_status") + SORT_ICONS[None], anchor="w",
                 command=lambda: app._on_sort_click("status"))
    tree.heading("poptracker", text=t("col_poptracker") + SORT_ICONS[None], anchor="w",
                 command=lambda: app._on_sort_click("poptracker"))
    tree.heading("notes",      text=t("col_notes"), anchor="w")
    tree.heading("owned",      text=t("col_owned") + SORT_ICONS[None], anchor="w",
                 command=lambda: app._on_sort_click("owned"))

    tree.column("game",       width=220, minwidth=130, stretch=False)
    tree.column("status",     width=120, minwidth=90,  stretch=False)
    tree.column("poptracker", width=100, minwidth=80,  stretch=False)
    tree.column("notes",      width=430, minwidth=160, stretch=True)
    tree.column("owned",      width=70,  minwidth=60,  stretch=False)

    vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    for status, color in STATUS_COLORS.items():
        tree.tag_configure(status, foreground=color)
    tree.tag_configure("Other",    foreground=TEXT_DIM)
    tree.tag_configure("new",      background="#1a2e1a")
    tree.tag_configure("core_yes", foreground=GREEN)
    tree.tag_configure("core_no",  foreground=RED)
    tree.tag_configure("odd_row",  background="#0d1117")
    tree.tag_configure("even_row", background="#161b22")

    return tree


def apply_columns(tree, tab, sort_col, sort_asc):
    """Adjust column visibility for the active tab."""
    is_core = tab == "Core Verified"
    if is_core:
        tree.column("status", width=0, minwidth=0, stretch=False)
        tree.heading("status", text="")
        tree.column("game",  width=260, minwidth=140)
        tree.column("notes", width=480, minwidth=180)
    else:
        tree.column("status", width=120, minwidth=90, stretch=False)
        tree.heading("status", text=t("col_status") + SORT_ICONS[
            sort_asc if sort_col == "status" else None])
        tree.column("game",  width=220, minwidth=130)
        tree.column("notes", width=430, minwidth=160)


def update_heading_icons(tree, tab, sort_col, sort_asc):
    is_core = tab == "Core Verified"
    cols_labels = {"game": t("col_game"), "poptracker": t("col_poptracker"), "owned": t("col_owned")}
    if not is_core:
        cols_labels["status"] = t("col_status")
    for col, label in cols_labels.items():
        icon = SORT_ICONS[sort_asc] if sort_col == col else SORT_ICONS[None]
        tree.heading(col, text=label + icon)


def sort_key(item, sort_col):
    name, data, has_pt, is_owned = item
    if sort_col == "game":
        return name.lower()
    elif sort_col == "status":
        return (STATUS_ORDER.get(data.get("status", ""), 99), name.lower())
    elif sort_col == "poptracker":
        return (0 if has_pt else 1, name.lower())
    elif sort_col == "owned":
        return (0 if is_owned else 1, name.lower())
    return name.lower()


def refresh_table(tree, app):
    """Repopulate the treeview from app state."""
    for item in tree.get_children():
        tree.delete(item)

    tab   = app._tab_var.get()
    games = app._all_games.get(tab, {})
    if not isinstance(games, dict):
        return

    query      = app._filter_var.get().lower()
    sf         = app._status_filter.get()
    pt_filt    = app._pt_filter.get()
    owned_filt = app._owned_filter.get()
    new_names  = {e[2] for e in app._changes if e[0] == "➕" and e[1] == tab}
    is_core    = tab == "Core Verified"

    filtered = []
    for name, data in games.items():
        if not isinstance(data, dict):
            continue
        status   = data.get("status", "")
        notes    = data.get("notes",  "")
        has_pt   = match_poptracker(name, app._poptracker_set)
        is_owned = is_owned_on_steam(name, app._steam_owned)

        if query and query not in name.lower() \
                 and query not in status.lower() \
                 and query not in notes.lower():
            continue
        if sf != "All":
            if sf == "Other":
                if status in STATUS_COLORS: continue
            elif status != sf:
                continue
        if pt_filt == " Disponible"     and not has_pt:   continue
        if pt_filt == " Non disponible" and has_pt:       continue
        if owned_filt == " YES"         and not is_owned: continue
        if owned_filt == " NO"          and is_owned:     continue

        filtered.append((name, data, has_pt, is_owned))

    if app._sort_col is not None:
        filtered.sort(key=lambda x: sort_key(x, app._sort_col),
                      reverse=(app._sort_asc is False))
    else:
        filtered.sort(key=lambda x: x[0].lower())

    for idx, (name, data, has_pt, is_owned) in enumerate(filtered):
        status    = data.get("status", "")
        notes     = data.get("notes",  "")
        pt_txt    = "YES" if has_pt   else "NO"
        owned_txt = "YES" if is_owned else "NO"

        if is_core:
            row_tag = "core_yes" if has_pt else "core_no"
        else:
            row_tag = status if status in STATUS_COLORS else "Other"

        stripe = "even_row" if idx % 2 == 0 else "odd_row"
        tags   = [stripe, row_tag] + (["new"] if name in new_names else [])
        tree.insert("", "end",
                    values=(name, status, pt_txt, notes, owned_txt),
                    tags=tags)

    app._count_lbl.config(text=t("count_label", n=len(filtered)))