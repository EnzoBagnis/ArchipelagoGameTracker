import tkinter as tk
import webbrowser
import re

from config import (
    BG2, BORDER, TEXT, TEXT_DIM, ACCENT2, GREEN, RED, YELLOW, STATUS_COLORS
)
from data import match_poptracker, extract_urls
from lang.l18n import t

URL_PATTERN = re.compile(r'https?://\S+')


def _sel_label(parent, text, bg, fg, font, anchor="w", wraplength=0, **kw):
    """
    Read-only Text widget styled as a Label: selectable text, no border,
    no edit cursor visuals. Falls back gracefully on wrap if wraplength given.
    """
    # Estimate height from wraplength (rough — 1 line if wraplength generous)
    w = tk.Text(parent, height=1, bg=bg, fg=fg, font=font,
                relief="flat", borderwidth=0, highlightthickness=0,
                wrap="none", cursor="xterm", state="normal",
                padx=0, pady=0, **kw)
    w.insert("1.0", text)
    w.config(state="disabled")
    return w


def build_detail_panel(parent):
    """
    Build the bottom detail panel inside `parent`.
    Returns a dict of widget references needed by update_detail().
    """
    tk.Frame(parent, bg=BORDER, height=1).pack(fill="x")

    detail = tk.Frame(parent, bg=BG2)
    detail.pack(fill="x")

    detail_top = tk.Frame(detail, bg=BG2, padx=14, pady=8)
    detail_top.pack(fill="x")

    title_lbl = _sel_label(detail_top,
                           text=t("detail_placeholder"),
                           bg=BG2, fg=TEXT_DIM,
                           font=("Courier New", 10, "bold"))
    title_lbl.pack(side="left", fill="x", expand=True)

    status_lbl = tk.Label(detail_top, text="", bg=BG2, fg=TEXT,
                          font=("Courier New", 9), anchor="e")
    status_lbl.pack(side="right", padx=(8, 0))

    pt_lbl = tk.Label(detail_top, text="", bg=BG2, fg=TEXT,
                      font=("Courier New", 9), anchor="e")
    pt_lbl.pack(side="right")

    detail_rel = tk.Frame(detail, bg=BG2, padx=14, pady=2)
    detail_rel.pack(fill="x")
    tk.Label(detail_rel, text=t("detail_release_label"), bg=BG2, fg=TEXT_DIM,
             font=("Courier New", 9), width=12, anchor="w").pack(side="left")
    release_lbl = tk.Label(detail_rel, text="—", bg=BG2,
                           fg=TEXT_DIM, font=("Courier New", 9), anchor="w")
    release_lbl.pack(side="left")

    notes_lbl = _sel_label(detail, text="", bg=BG2, fg=TEXT_DIM,
                           font=("Courier New", 9))
    notes_lbl.pack(fill="x", padx=14)
    detail.bind("<Configure>",
                lambda e: None)  # wraplength not needed — Text wraps via width

    links_frame = tk.Frame(detail, bg=BG2, padx=14, pady=4)
    links_frame.pack(fill="x")

    return {
        "title":   title_lbl,
        "status":  status_lbl,
        "pt":      pt_lbl,
        "release": release_lbl,
        "notes":   notes_lbl,
        "links":   links_frame,
    }


def _set_sel_label(widget, text, fg=None):
    """Update content and optionally color of a selectable (_sel_label) Text widget."""
    widget.config(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", text)
    if fg:
        widget.config(fg=fg)
    widget.config(state="disabled")


def update_detail(widgets, name, status, notes, tab, releases, poptracker_set, apworld="", links=None):
    """Populate the detail panel for the selected game."""
    w = widgets

    _set_sel_label(w["title"], name, fg=TEXT)
    color = STATUS_COLORS.get(status, TEXT_DIM)
    w["status"].config(text="● " + status if status else "", fg=color)

    # PopTracker
    has_pt = match_poptracker(name, poptracker_set)
    if has_pt:
        wiki_url = "https://archipelago.miraheze.org/wiki/" + name.replace(" ", "_")
        w["pt"].config(text=t("detail_pt_yes"), fg=GREEN, cursor="hand2")
        w["pt"].bind("<Button-1>", lambda e, u=wiki_url: webbrowser.open(u))
    else:
        w["pt"].config(text=t("detail_pt_no"), fg=RED, cursor="")
        w["pt"].unbind("<Button-1>")

    # Release
    w["release"].unbind("<Button-1>")
    rel = releases.get(tab, {}).get(name)
    if rel and rel.get("tag"):
        tag_str  = rel["tag"]
        date_str = rel.get("date", "")
        rel_url  = rel.get("url", "")
        label    = (tag_str + "  —  " + date_str) if date_str else tag_str
        if rel_url:
            w["release"].config(text=label + "  ↗", fg=ACCENT2,
                                font=("Courier New", 9, "underline"), cursor="hand2")
            w["release"].bind("<Button-1>",
                              lambda e, u=rel_url: webbrowser.open(u))
        else:
            w["release"].config(text=label, fg=YELLOW,
                                font=("Courier New", 9), cursor="")
    else:
        w["release"].config(text="—", fg=TEXT_DIM,
                            font=("Courier New", 9), cursor="")

    # ── Links ─────────────────────────────────────────────────────────────────
    # Priority: structured links list (new sheet format) > legacy apworld field
    for child in w["links"].winfo_children():
        child.destroy()

    if links:
        # New format: render each {label, url} pair directly
        for link in links:
            label_txt = link.get("label", "").strip()
            url       = link.get("url", "").strip()
            if not url:
                continue
            row = tk.Frame(w["links"], bg=BG2)
            row.pack(anchor="w", pady=1)
            tk.Label(row, text=label_txt if label_txt else "🔗",
                     bg=BG2, fg=TEXT_DIM,
                     font=("Courier New", 9), width=20, anchor="w").pack(side="left")
            short = _short_url(url)
            lnk = tk.Label(row, text=short, bg=BG2, fg=ACCENT2,
                           font=("Courier New", 9, "underline"),
                           cursor="hand2", anchor="w")
            lnk.pack(side="left")
            lnk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            lnk.bind("<Enter>",    lambda e, l=lnk: l.config(fg="#c084fc"))
            lnk.bind("<Leave>",    lambda e, l=lnk: l.config(fg=ACCENT2))

        # Notes plain text (no links to extract — they're already in `links`)
        _set_sel_label(w["notes"], notes if notes else "")
    else:
        # Legacy format: parse apworld + notes for URLs
        apworld_links, apworld_plain = _parse_notes(apworld)
        labeled_links, plain_text    = _parse_notes(notes)

        all_plain = []
        if apworld_plain:
            all_plain.append(apworld_plain)
        if plain_text:
            all_plain.append(plain_text)
        _set_sel_label(w["notes"], " • ".join(all_plain) if all_plain else "")

        for label, url in apworld_links:
            row = tk.Frame(w["links"], bg=BG2)
            row.pack(anchor="w", pady=1)
            lbl_text = label if label else "APWorld/Client:"
            tk.Label(row, text=lbl_text, bg=BG2, fg=TEXT_DIM,
                     font=("Courier New", 9), width=16, anchor="w").pack(side="left")
            short = _short_url(url)
            lnk = tk.Label(row, text=short, bg=BG2, fg=ACCENT2,
                           font=("Courier New", 9, "underline"),
                           cursor="hand2", anchor="w")
            lnk.pack(side="left")
            lnk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            lnk.bind("<Enter>",    lambda e, l=lnk: l.config(fg="#c084fc"))
            lnk.bind("<Leave>",    lambda e, l=lnk: l.config(fg=ACCENT2))

        for label, url in labeled_links:
            row = tk.Frame(w["links"], bg=BG2)
            row.pack(anchor="w", pady=1)
            lbl_text = label if label else "🔗"
            tk.Label(row, text=lbl_text, bg=BG2, fg=TEXT_DIM,
                     font=("Courier New", 9), width=16, anchor="w").pack(side="left")
            short = _short_url(url)
            lnk = tk.Label(row, text=short, bg=BG2, fg=ACCENT2,
                           font=("Courier New", 9, "underline"),
                           cursor="hand2", anchor="w")
            lnk.pack(side="left")
            lnk.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
            lnk.bind("<Enter>",    lambda e, l=lnk: l.config(fg="#c084fc"))
            lnk.bind("<Leave>",    lambda e, l=lnk: l.config(fg=ACCENT2))


def _parse_notes(notes):
    if not notes:
        return [], ""
    labeled     = []
    plain_parts = []
    for line in notes.replace("\\n", "\n").splitlines():
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


def _short_url(url):
    try:
        from urllib.parse import urlparse
        p    = urlparse(url)
        host = p.netloc.replace("www.", "")
        path = p.path[:35] + ("…" if len(p.path) > 35 else "")
        return host + path
    except Exception:
        return url[:50] + "…"