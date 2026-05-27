import re
import csv
import io
import unicodedata

import requests

from config import (
    SHEET_ID, TABS, POPTRACKER_API, GITHUB_REPO_RE, SKIP_NAMES
)

URL_PATTERN = re.compile(r'https?://\S+')

# ── HTML link label normalisation ─────────────────────────────────────────────
# Maps the text labels used in the "Links & Downloads" column to short keys
# that the detail panel can display clearly.
_LINK_LABEL_MAP = {
    # GitHub
    "github releases":          "GitHub Releases",
    "releases":                 "GitHub Releases",
    "github release":           "GitHub Releases",
    # APWorld / Client
    "apworld":                  "APWorld",
    "ap world":                 "APWorld",
    "client":                   "Client",
    "client mod":               "Client Mod",
    "client (gh)":              "Client (GH)",
    "client (thunderstore)":    "Client (Thunderstore)",
    "client (web)":             "Client (Web)",
    "must be compiled":         "Client",
    # Guides / info
    "setup guide":              "Setup Guide",
    "setup instructions":       "Setup Instructions",
    "game info":                "Game Info",
    "game details":             "Game Details",
    "documentation":            "Documentation",
    "docs":                     "Docs",
    "extensive docs":           "Docs",
    "faq":                      "FAQ",
    "guide / docs":             "Guide / Docs",
    "known bugs":               "Known Bugs",
    "options page":             "Options Page",
    # Trackers
    "poptracker":               "PopTracker",
    "tracker":                  "Tracker",
    "universal tracker":        "Universal Tracker",
    # Storefronts / release hosts
    "itch.io releases":         "Itch.io",
    "discord releases":         "Discord",
    "discord thread":           "Discord Thread",
    "discord channel":          "Discord",
    "gitlab releases":          "GitLab Releases",
    # Misc
    "core pr":                  "Core PR",
    "source code":              "Source Code",
    "web client":               "Web Client",
    "play on web":              "Play on Web",
    "mod":                      "Mod",
    "beta testing discord":     "Beta Testing",
    "live split mod":           "LiveSplit Mod",
    "releases + setup instructions": "Releases + Setup",
    "discord releases, core pr":     "Discord / Core PR",
    "game (free via gog)":      "Game (Free - GOG)",
    "dev branch":               "Dev Branch",
}


def _normalise_link_label(raw: str) -> str:
    """Return a cleaned display label for a hyperlink's anchor text."""
    key = raw.strip().lower()
    return _LINK_LABEL_MAP.get(key, raw.strip())


# ── Sheet fetching ─────────────────────────────────────────────────────────────

def fetch_tab(tab_name, gid):
    """
    Fetch a sheet tab as CSV rows (no hyperlinks preserved).
    Returns list of string lists, used as fallback only.
    """
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
           f"/export?format=csv&gid={gid}")
    try:
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "GameSupportTracker/1.0"})
    except Exception:
        return []
    if r.status_code != 200:
        return []
    return list(csv.reader(io.StringIO(r.content.decode("utf-8"))))


def fetch_tab_with_links(tab_name, gid):
    """
    Fetch a sheet tab via its HTML export, which preserves <a href> hyperlinks
    in the "Links & Downloads" column.

    Returns a list of row-dicts:
      {
        "name":   str,
        "status": str,
        "pr":     str,
        "links":  [{"label": str, "url": str}, ...],
        "mature": bool,
        "notes":  str,
      }

    Falls back to the CSV path (no links) if the HTML fetch/parse fails.
    """
    try:
        from html.parser import HTMLParser

        url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
               f"/export?format=html&gid={gid}")
        r = requests.get(url, timeout=20,
                         headers={"User-Agent": "GameSupportTracker/1.0"})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")

        html_text = r.content.decode("utf-8", errors="replace")

        # ── Minimal HTML-table parser ────────────────────────────────────────
        class _TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.rows:      list[list]  = []
                self._cur_row:  list        = []
                self._cur_cell: list        = []   # list of (text, url) pairs
                self._in_td    = False
                self._cur_href = None
                self._cur_text = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag in ("tr",):
                    self._cur_row  = []
                elif tag in ("td", "th"):
                    self._in_td    = True
                    self._cur_cell = []
                    self._cur_href = None
                    self._cur_text = []
                elif tag == "a" and self._in_td:
                    self._cur_href = attrs.get("href", "")
                    self._cur_text = []

            def handle_endtag(self, tag):
                if tag == "a" and self._in_td and self._cur_href is not None:
                    text = "".join(self._cur_text).strip()
                    self._cur_cell.append((text, self._cur_href))
                    self._cur_href = None
                    self._cur_text = []
                elif tag in ("td", "th") and self._in_td:
                    # Flush any remaining plain text as (text, "")
                    remaining = "".join(self._cur_text).strip()
                    if remaining:
                        self._cur_cell.append((remaining, ""))
                    self._cur_row.append(self._cur_cell)
                    self._in_td    = False
                    self._cur_cell = []
                    self._cur_text = []
                    self._cur_href = None
                elif tag == "tr":
                    if self._cur_row:
                        self.rows.append(self._cur_row)
                    self._cur_row = []

            def handle_data(self, data):
                if self._in_td:
                    self._cur_text.append(data)

        parser = _TableParser()
        parser.feed(html_text)

        # ── Convert parsed rows to dicts ─────────────────────────────────────
        # New sheet structure (Playable Worlds):
        #   col 0: Game name
        #   col 1: Stability   (Stable / Unstable / Broken on Main / …)
        #   col 2: PR Status   (--, In Review, Merged, Not PRing)
        #   col 3: Links & Downloads  ← multi-hyperlink cell
        #   col 4: 18+ / Unrated      (TRUE / FALSE)
        #   col 5: Notes
        #
        # Core Verified:
        #   col 0: Game name
        #   col 1: Game Page link
        #   col 2: Setup Guide link
        #   col 3: Discord Channel link

        is_core = (tab_name == "Core Verified")
        result_rows = []

        for raw_row in parser.rows:
            def _cell_text(i):
                """Plain text of cell i."""
                if i >= len(raw_row):
                    return ""
                return " ".join(t for t, _ in raw_row[i]).strip()

            def _cell_links(i):
                """List of {label, url} for cell i (only pairs with a URL)."""
                if i >= len(raw_row):
                    return []
                return [
                    {"label": _normalise_link_label(t), "url": u}
                    for t, u in raw_row[i]
                    if u and t.strip()
                ]

            name = _cell_text(0)
            if not name or name in SKIP_NAMES or len(name) > 120:
                continue

            if is_core:
                # Core Verified — links scattered across cols 1-3
                links = (
                    _cell_links(1) + _cell_links(2) + _cell_links(3)
                )
                result_rows.append({
                    "name":   name,
                    "status": "Core Verified",
                    "pr":     "",
                    "links":  links,
                    "mature": False,
                    "notes":  "",
                })
            else:
                status = _cell_text(1)
                if status.lower() in ("status", "game", "do not sort",
                                      "stability", ""):
                    continue
                pr     = _cell_text(2)
                links  = _cell_links(3)
                mature_raw = _cell_text(4).strip().upper()
                mature = mature_raw in ("TRUE", "YES", "1")
                notes  = _cell_text(5)
                result_rows.append({
                    "name":   name,
                    "status": status,
                    "pr":     pr,
                    "links":  links,
                    "mature": mature,
                    "notes":  notes,
                })

        return result_rows

    except Exception:
        # ── Fallback: CSV path (no links) ────────────────────────────────────
        csv_rows = fetch_tab(tab_name, gid)
        return _csv_rows_to_dicts(csv_rows, tab_name)


def _csv_rows_to_dicts(rows, tab_name):
    """
    Convert raw CSV rows (no hyperlinks) to the same row-dict format as
    fetch_tab_with_links(), but with empty link lists.
    New sheet structure: A=Game B=Stability C=PR D=LinksText E=18+ F=Notes
    """
    is_core = (tab_name == "Core Verified")
    result  = []
    for row in rows:
        if not row:
            continue
        name = row[0].strip() if row else ""
        if not name or name in SKIP_NAMES or len(name) > 120:
            continue

        def _get(i):
            return row[i].strip() if i < len(row) else ""

        if is_core:
            result.append({
                "name":   name,
                "status": "Core Verified",
                "pr":     "",
                "links":  [],
                "mature": False,
                "notes":  "",
            })
        else:
            status = _get(1)
            if status.lower() in ("status", "game", "do not sort",
                                  "stability", ""):
                continue
            # col 2 = PR status, col 3 = links text, col 4 = mature, col 5 = notes
            pr     = _get(2)
            links_text = _get(3)
            mature = _get(4).strip().upper() in ("TRUE", "YES", "1")
            notes  = _get(5)
            # Best effort: extract any raw URLs from the links text column
            links = [{"label": u, "url": u} for u in URL_PATTERN.findall(links_text)]
            result.append({
                "name":   name,
                "status": status,
                "pr":     pr,
                "links":  links,
                "mature": mature,
                "notes":  notes,
            })
    return result


def rows_to_dict(rows, tab_name=""):
    """
    Convert raw CSV rows (old format) into the legacy
    {name: {status, notes, apworld}} dict used by _do_check.

    New sheet column layout (Playable Worlds):
      A(0)=Game  B(1)=Stability  C(2)=PR Status  D(3)=Links  E(4)=18+  F(5)=Notes

    Core Verified:
      A(0)=Game  B(1)=Game Page  C(2)=Setup Guide  D(3)=Discord

    The 'apworld' key is derived from the first link URL found in col D.
    """
    if not rows:
        return {}

    is_core = (tab_name == "Core Verified")
    result  = {}

    for row in rows:
        if not row:
            continue
        name = row[0].strip()
        if not name or name in SKIP_NAMES or len(name) > 120:
            continue

        def _get(i):
            return row[i].strip() if i < len(row) else ""

        if is_core:
            status  = "Core Verified"
            apworld = ""
            notes   = ""
        else:
            status = _get(1)
            if status.lower() in ("status", "game", "do not sort",
                                  "stability", ""):
                continue
            # col 3 = links text cell (plain text from CSV — no real URLs)
            # col 5 = notes
            links_text = _get(3)
            notes      = _get(5)
            # Try to pick up any raw URL accidentally present in the links column
            found_urls = URL_PATTERN.findall(links_text)
            apworld    = found_urls[0] if found_urls else ""

        result[name] = {"status": status, "notes": notes, "apworld": apworld}
    return result


# ── URL helpers ────────────────────────────────────────────────────────────────

def extract_urls(text):
    return URL_PATTERN.findall(text)


def extract_github_repo(notes, apworld="", links=None):
    """
    Return (owner, repo) from the first valid GitHub URL found, or None.

    Accepts:
      notes   – plain-text notes string (old + new format)
      apworld – legacy apworld URL string
      links   – list of {"label": str, "url": str} dicts (new format)
    """
    # 1. Prefer the structured links list (new sheet format)
    if links:
        for link in links:
            url = link.get("url", "")
            if not url:
                continue
            m = GITHUB_REPO_RE.search(url)
            if m:
                owner = m.group(1)
                repo  = m.group(2)
                if repo.endswith(".git"):
                    repo = repo[:-4]
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if "/pull/" in parsed.path:
                    continue
                return owner, repo

    # 2. Fallback: scan free-text fields (legacy / CSV fallback)
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
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if "/pull/" in parsed.path:
                    continue
                return owner, repo
    return None


# ── GitHub ─────────────────────────────────────────────────────────────────────

def fetch_github_release(owner, repo, token=""):
    """Return {tag, date, url}, None on error, or 'rate_limited' on 403/429."""
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        headers = {
            "User-Agent": "GameSupportTracker/1.0",
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


# ── PopTracker ─────────────────────────────────────────────────────────────────

def _normalize(name):
    n = name.lower()
    for prefix in ["category:", "game:"]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    n = re.sub(r"[:\-_'\"!.,&()]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def fetch_poptracker_games():
    try:
        headers = {"User-Agent": "GameSupportTracker/1.0"}
        r = requests.get(POPTRACKER_API, timeout=15, headers=headers)
        if r.status_code != 200:
            return set()
        data    = r.json()
        members = data.get("query", {}).get("categorymembers", [])
        return {_normalize(m.get("title", "")) for m in members}
    except Exception:
        return set()


def match_poptracker(game_name, poptracker_set):
    norm = _normalize(game_name)
    if norm in poptracker_set:
        return True
    for pt in poptracker_set:
        if norm in pt or pt in norm:
            if len(norm) > 4 and len(pt) > 4:
                return True
    return False


# ── Steam ──────────────────────────────────────────────────────────────────────

def _extract_acronym(name: str) -> str | None:
    """'Totally Accurate Battle Simulator (TABS)' -> 'tabs'"""
    match = re.search(r'\(([A-Z]{2,})\)', name)
    return match.group(1).lower() if match else None


def _normalize_steam(name: str) -> set[str]:
    """
    Returns a set of normalised variants for `name`.
    Used to build the owned-games lookup set AND to query it.

    Variant types produced:
      • base       – cleaned lowercase name, no punctuation   (always)
      • explicit   – acronym written in parens like "(TABS)"  (always when present)
      • generated  – acronym built from initials              (only for 3+ significant words)

    False-positive guard: a *generated* acronym is only safe when the source
    name has 3+ significant words.  Short titles like "LIS" or "NMS" produce
    only a base variant; their base won't collide with a generated acronym
    because `is_owned_on_*` uses asymmetric matching (see below).
    """
    clean = re.sub(r'\s*\(.*?\)', '', name).strip()
    base  = re.sub(r"[^a-z0-9 ]", "", clean.lower()).strip()

    variants = {base}

    # Explicit acronym in parens — always reliable
    explicit = _extract_acronym(name)
    if explicit:
        variants.add(explicit)

    # Generated acronym — only for names with 3+ significant words
    #STOP  = {"a", "an", "the", "of", "vs", "vs.", "and", "&", "in", "on",
    #         "at", "to", "for", "is", "be"}
    #words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", " ", clean).split()
    #         if w.lower() not in STOP and w[0].isalpha()]
    #if len(words) >= 3:
    #    acronym = "".join(w[0] for w in words).lower()
    #    if len(acronym) >= 3:
    #        variants.add(acronym)

    return variants


def _normalize_steam_typed(name: str) -> dict:
    """
    Same as _normalize_steam but returns variants split by type:
      {"base": str, "explicit": str|None, "generated": str|None}
    Used for asymmetric matching to prevent false positives.
    """
    clean    = re.sub(r'\s*\(.*?\)', '', name).strip()
    base     = re.sub(r"[^a-z0-9 ]", "", clean.lower()).strip()
    explicit = _extract_acronym(name)

    STOP  = {"a", "an", "the", "of", "vs", "vs.", "and", "&", "in", "on",
             "at", "to", "for", "is", "be"}
    words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", " ", clean).split()
             if w.lower() not in STOP and w[0].isalpha()]
    generated = None
    if len(words) >= 3:
        acr = "".join(w[0] for w in words).lower()
        if len(acr) >= 3:
            generated = acr

    return {"base": base, "explicit": explicit, "generated": generated}


def _is_match(sheet_name: str, owned_bases: set[str], owned_all: set[str]) -> bool:
    """
    Asymmetric match to avoid false positives:

    • sheet base / explicit  →  match against owned_all  (permissive)
    • sheet generated acronym →  match only against owned_bases  (strict)
      — this prevents "Life is Strange" (LIS) matching a Steam game called "LIS"
    """
    st = _normalize_steam_typed(sheet_name)

    # Base name exact match (e.g. "hollow knight silksong" == "hollow knight silksong")
    if st["base"] in owned_all:
        return True

    # Explicit acronym in parens — always reliable
    if st["explicit"] and st["explicit"] in owned_all:
        return True

    # Generated acronym — only match against base names, NOT other generated acronyms
    if st["generated"] and st["generated"] in owned_bases:
        return True

    return False


# ── Alias table ────────────────────────────────────────────────────────────────
# Maps sheet_name (lowercase) → frozenset of lowercase aliases
# Built once from aliases.xlsx; queried by is_owned_on_* functions.

_alias_map: dict[str, frozenset[str]] = {}   # sheet_base → {alias_base, ...}
_alias_path: str = ""


def load_alias_table(path: str) -> int:
    """
    Read aliases.xlsx and populate the global alias map.
    Returns the number of rows loaded.
    Column layout (matches generate_aliases.py):
      A: Sheet Name  B: Aliases (comma-separated)  C: Done  D: Tab
    """
    global _alias_map, _alias_path
    _alias_map  = {}
    _alias_path = path

    if not path:
        return 0

    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        count = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            sheet_name = str(row[0]).strip()
            aliases_raw = str(row[1]).strip() if row[1] else sheet_name
            if not sheet_name:
                continue
            # Normalise each alias the same way as steam names
            alias_bases: set[str] = set()
            for alias in aliases_raw.split(","):
                alias = alias.strip()
                if alias:
                    base = re.sub(r"[^a-z0-9 ]", "",
                                  re.sub(r'\s*\(.*?\)', '', alias).lower()).strip()
                    if base:
                        alias_bases.add(base)
            # Also store the sheet name itself as a base
            sheet_base = re.sub(r"[^a-z0-9 ]", "",
                                re.sub(r'\s*\(.*?\)', '', sheet_name).lower()).strip()
            alias_bases.add(sheet_base)
            _alias_map[sheet_base] = frozenset(alias_bases)
            count += 1
        wb.close()
        return count
    except Exception:
        _alias_map = {}
        return 0


def get_sheet_aliases(sheet_name: str) -> frozenset[str]:
    """
    Return all known aliases for a sheet game name (including itself).
    Falls back to _normalize_steam variants if no alias table is loaded.
    """
    if not _alias_map:
        return frozenset(_normalize_steam(sheet_name))
    base = re.sub(r"[^a-z0-9 ]", "",
                  re.sub(r'\s*\(.*?\)', '', sheet_name).lower()).strip()
    if base in _alias_map:
        return _alias_map[base]
    # Not in table — fall back to auto-normalization for this game
    return frozenset(_normalize_steam(sheet_name))


def _is_match_with_aliases(sheet_name: str,
                            owned_bases: set[str],
                            owned_all: set[str]) -> bool:
    """
    Match using alias table when available, otherwise asymmetric acronym matching.
    Any alias of the sheet game that appears in owned_all is a hit.
    """
    if _alias_map:
        aliases = get_sheet_aliases(sheet_name)
        return bool(aliases & owned_all)
    return _is_match(sheet_name, owned_bases, owned_all)


def fetch_steam_owned(api_key, steam_ids):
    """Return dict of {frozenset_of_variants: original_name} owned across all given Steam IDs."""
    owned = {}
    headers = {"User-Agent": "GameSupportTracker/1.0"}
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

    # Build variant sets: all_variants for general lookup, bases for acronym guard
    all_variants: set[str] = set()
    base_variants: set[str] = set()
    for name in owned.values():
        if name:
            typed = _normalize_steam_typed(name)
            base_variants.add(typed["base"])
            all_variants.add(typed["base"])
            if typed["explicit"]:
                all_variants.add(typed["explicit"])
            if typed["generated"]:
                all_variants.add(typed["generated"])

    return all_variants, base_variants, len(owned)


def is_owned_on_steam(sheet_name: str, steam_variants: set[str],
                      steam_bases: set[str] | None = None) -> bool:
    if steam_bases is None:
        return bool(_normalize_steam(sheet_name) & steam_variants)
    return _is_match_with_aliases(sheet_name, steam_bases, steam_variants)


# ── Playnite ───────────────────────────────────────────────────────────────────
# Reads the games.db file from a Playnite backup ZIP.
# Playnite stores its library in a LiteDB binary format. We parse it directly
# by locating BSON "Favorite" boolean fields (present exactly once per game
# document) and scanning backwards for the game's Name field.
#
# How the user creates the backup:
#   Playnite main menu (☰) → Library → Save library data
#   → saves a .zip file the user can select in GST settings.

def _parse_games_db(db_bytes: bytes) -> list[str]:
    """
    Extract game names from a Playnite games.db (LiteDB/BSON) binary blob.
    Returns a list of unique game name strings.

    Strategy:
      - Use \\x08Favorite\\x00 as the anchor: this boolean field appears exactly
        once per game document, even for games without a store ID.
      - Walk backwards (up to 80 KB) from each anchor to find the last
        \\x02Name\\x00 field that belongs to the game doc, skipping:
          * Link sub-document names (Name immediately followed by Url)
          * CompletionStatus names (Name immediately followed by RecentActivity)
      - Also check 50 KB forward for edge cases where the Name segment lands
        after the Favorite in the file (heavily fragmented docs).
    """
    import struct

    fav_needle    = b'\x08Favorite\x00'
    name_needle   = b'\x02Name\x00'
    url_needle    = b'\x02Url\x00'
    recent_needle = b'RecentActivity'
    LOOK_BACK     = 80_000
    LOOK_FWD      = 50_000

    def _read_bson_string(data, pos):
        if pos + 4 > len(data):
            return None
        n = struct.unpack_from('<I', data, pos)[0]
        if not (1 <= n <= 512):
            return None
        end = pos + 4 + n - 1
        if end > len(data):
            return None
        v = data[pos + 4:end].decode('utf-8', errors='replace')
        return None if ('\x00' in v or v.count('\ufffd') > 1) else v

    def _find_game_name(data, anchor):
        """Search backwards then forwards from anchor for the game Name."""
        # ── backwards pass ────────────────────────────────────────────────
        window_start = max(0, anchor - LOOK_BACK)
        window = data[window_start:anchor]
        ni = len(window)
        while True:
            ni = window.rfind(name_needle, 0, ni)
            if ni == -1:
                break
            abs_ni  = window_start + ni
            candidate = _read_bson_string(data, abs_ni + len(name_needle))
            if not candidate:
                continue
            val_end = abs_ni + len(name_needle) + 4 + len(candidate)
            after   = data[val_end:val_end + 20]
            if url_needle in after or recent_needle in after:
                continue
            return candidate

        # ── forward pass (fragmented docs) ───────────────────────────────
        fwd_end = min(len(data), anchor + LOOK_FWD)
        ni = anchor
        while True:
            ni = data.find(name_needle, ni + 1, fwd_end)
            if ni == -1:
                break
            candidate = _read_bson_string(data, ni + len(name_needle))
            if not candidate:
                continue
            val_end = ni + len(name_needle) + 4 + len(candidate)
            after   = data[val_end:val_end + 20]
            if url_needle in after or recent_needle in after:
                continue
            return candidate

        return None

    games = []
    seen  = set()
    pos   = 0

    while True:
        fi = db_bytes.find(fav_needle, pos)
        if fi == -1:
            break
        pos = fi + 1

        name = _find_game_name(db_bytes, fi)
        if name and name not in seen:
            seen.add(name)
            games.append(name)

    return games


def load_playnite_library(path: str) -> tuple[set[str], set[str], int]:
    """
    Load a Playnite library from a backup ZIP and return
    (all_variants, base_variants, total_count).
    Returns (set(), set(), 0) on any error.
    """
    import zipfile

    try:
        with zipfile.ZipFile(path, 'r') as z:
            with z.open('library/games.db') as f:
                db_bytes = f.read()
    except Exception:
        return set(), set(), 0

    names = _parse_games_db(db_bytes)

    all_variants:  set[str] = set()
    base_variants: set[str] = set()
    for name in names:
        typed = _normalize_steam_typed(name)
        base_variants.add(typed["base"])
        all_variants.add(typed["base"])
        if typed["explicit"]:
            all_variants.add(typed["explicit"])
        if typed["generated"]:
            all_variants.add(typed["generated"])

    return all_variants, base_variants, len(names)


def is_owned_on_playnite(sheet_name: str, playnite_variants: set[str],
                         playnite_bases: set[str] | None = None) -> bool:
    if playnite_bases is None:
        return bool(_normalize_steam(sheet_name) & playnite_variants)
    return _is_match_with_aliases(sheet_name, playnite_bases, playnite_variants)