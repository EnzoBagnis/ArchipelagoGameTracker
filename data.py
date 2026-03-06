import re
import csv
import io
import unicodedata

import requests

from config import (
    SHEET_ID, TABS, POPTRACKER_API, GITHUB_REPO_RE, SKIP_NAMES
)

URL_PATTERN = re.compile(r'https?://\S+')


# ── Sheet ──────────────────────────────────────────────────────────────────────

def fetch_tab(tab_name, gid):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"
    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        return []
    return list(csv.reader(io.StringIO(r.content.decode("utf-8"))))


def rows_to_dict(rows, tab_name=""):
    """Parse raw CSV rows into {name: {status, notes, apworld}} dict."""
    if not rows:
        return {}

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

        if status.lower() in ("status", "game", "do not sort"):
            continue

        result[name] = {"status": status, "notes": notes, "apworld": apworld}
    return result


# ── URL helpers ────────────────────────────────────────────────────────────────

def extract_urls(text):
    return URL_PATTERN.findall(text)


def extract_github_repo(notes, apworld=""):
    """Return (owner, repo) from the first valid GitHub URL found, or None."""
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
                if "/pull/" in url:
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

def _build_acronym(name: str) -> str:
    """'Totally Accurate Battle Simulator' -> 'tabs'"""
    STOP = {"a", "an", "the", "of", "vs", "vs.", "and", "&", "in", "on", "at", "to", "for"}
    clean = re.sub(r"[^a-zA-Z0-9 ]", " ", name)
    words = clean.split()
    return "".join(w[0] for w in words if w.lower() not in STOP).lower()

def _normalize_steam(name: str) -> set[str]:
    """Retourne un set de variantes normalisées."""
    # Nom de base sans parenthèses
    clean = re.sub(r'\s*\(.*?\)', '', name).strip()
    base = re.sub(r"[^a-z0-9 ]", "", clean.lower())

    variants = {base}

    # Acronyme explicite: "Foo Bar (FB)" -> "fb"
    # Toujours fiable car écrit explicitement par Steam
    explicit = _extract_acronym(name)
    if explicit:
        variants.add(explicit)

    # Acronyme généré: "Totally Accurate Battle Simulator" -> "tabs"
    # Seulement si 3+ mots significatifs ET acronyme de 3+ caractères
    # → évite les faux positifs ("Hades" -> "h", "Hollow Knight" -> "hk")
    STOP = {"a", "an", "the", "of", "vs", "vs.", "and", "&", "in", "on", "at", "to", "for"}
    words = [w for w in re.sub(r"[^a-zA-Z0-9 ]", " ", clean).split()
             if w.lower() not in STOP and w[0].isalpha()]  # exclut les mots commençant par un chiffre
    if len(words) >= 3:
        acronym = "".join(w[0] for w in words).lower()
        if len(acronym) >= 3:
            variants.add(acronym)

    return variants


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

    # Construit un set "à plat" de toutes les variantes -> pour lookup rapide
    all_variants: set[str] = set()
    for name in owned.values():
        if name:
            for v in _normalize_steam(name):
                all_variants.add(v)

    return all_variants, len(owned)


def is_owned_on_steam(sheet_name: str, steam_variants: set[str]) -> bool:
    """Vérifie si un jeu du sheet est dans les variantes Steam."""
    return bool(_normalize_steam(sheet_name) & steam_variants)


# ── Itch.io ────────────────────────────────────────────────────────────────────
# Requires an OAuth access token with the `profile:owned` scope.
#
# How the user gets a token (no web server needed):
#   1. Go to https://itch.io/user/settings/oauth-apps → create an OAuth app
#   2. Set redirect URI to:  urn:ietf:wg:oauth:2.0:oob
#   3. Open in browser:
#      https://itch.io/oauth/authorize
#        ?client_id=YOUR_CLIENT_ID
#        &scope=profile%3Aowned
#        &response_type=token
#        &redirect_uri=urn%3Aietf%3Awg%3Aoauth%3A2.0%3Aoob
#   4. Authorize → itch.io shows the token on-screen → user copies it here.

ITCH_OWNED_URL = "https://api.itch.io/profile/owned-keys"


def fetch_itch_owned(token: str) -> tuple[set[str] | None, int]:
    """
    Return (variants_set, total_count) for all games owned on itch.io.
    Returns (None, 0) on error (bad token, network failure).
    Returns (set(), 0) on success with an empty library.
    """
    if not token:
        return None, 0

    headers = {
        "User-Agent":    "GameSupportTracker/1.0",
        "Authorization": f"Bearer {token}",
    }

    owned_names: list[str] = []
    page = 1

    while True:
        try:
            r = requests.get(
                ITCH_OWNED_URL,
                params={"page": page},
                headers=headers,
                timeout=15,
            )
        except Exception:
            return None, 0

        if r.status_code != 200:
            break

        data = r.json()
        keys = data.get("owned_keys", [])
        # itch.io returns {} (empty dict) when there are no results,
        # and either a list or dict with int keys when there are games.
        if isinstance(keys, dict):
            keys = list(keys.values())
        if not keys:
            break

        for entry in keys:
            game = entry.get("game") or {}
            name = game.get("title", "").strip()
            if name:
                owned_names.append(name)

        # itch.io paginates in chunks of 50; stop when we get a short page
        if len(keys) < 50:
            break
        page += 1

    all_variants: set[str] = set()
    for name in owned_names:
        all_variants.update(_normalize_steam(name))   # reuse same normaliser

    return all_variants, len(owned_names)


def is_owned_on_itch(sheet_name: str, itch_variants: set[str]) -> bool:
    return bool(_normalize_steam(sheet_name) & itch_variants)


# ── Playnite ───────────────────────────────────────────────────────────────────
# Playnite can export the full library as a JSON file.
# How the user exports:
#   Main menu → Library → Export Library…  (Playnite 10+)
#   Or via the built-in script:  Start-Process playnite://playnite/exportlibrary
#
# The exported JSON is a list of game objects; the fields we care about are:
#   "Name"        – display name  (always present)
#   "Source"      – e.g. "Steam", "GOG", "Epic Games", "itch.io", "Xbox"
#   "IsInstalled" – bool (we index everything, installed or not)

def load_playnite_library(path: str) -> tuple[set[str], int]:
    """
    Parse a Playnite JSON export and return (variants_set, total_count).
    variants_set is compatible with is_owned_on_steam() / is_owned_on_itch().
    Returns (set(), 0) if the file can't be read or is malformed.
    """
    import json

    try:
        with open(path, "r", encoding="utf-8") as f:
            games: list[dict] = json.load(f)
    except Exception:
        return set(), 0

    if not isinstance(games, list):
        return set(), 0

    all_variants: set[str] = set()
    count = 0

    for game in games:
        name = (game.get("Name") or "").strip()
        if not name:
            continue
        all_variants.update(_normalize_steam(name))
        count += 1

    return all_variants, count


def is_owned_on_playnite(sheet_name: str, playnite_variants: set[str]) -> bool:
    return bool(_normalize_steam(sheet_name) & playnite_variants)