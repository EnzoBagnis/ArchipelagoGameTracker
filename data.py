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
        headers = {"User-Agent": "ArchipelagoTracker/1.0"}
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
    explicit = _extract_acronym(name)
    if explicit:
        variants.add(explicit)

    # Acronyme généré depuis le nom nettoyé: "Totally Accurate Battle Simulator" -> "tabs"
    variants.add(_build_acronym(clean))

    return variants


def fetch_steam_owned(api_key, steam_ids):
    """Return dict of {frozenset_of_variants: original_name} owned across all given Steam IDs."""
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

    # Construit un set "à plat" de toutes les variantes -> pour lookup rapide
    all_variants: set[str] = set()
    variant_map: dict[str, str] = {}  # variante -> nom original (optionnel, pour debug)
    for name in owned.values():
        if name:
            for v in _normalize_steam(name):
                all_variants.add(v)
                variant_map[v] = name

    return all_variants


def is_owned_on_steam(sheet_name: str, steam_variants: set[str]) -> bool:
    """Vérifie si un jeu du sheet est dans les variantes Steam."""
    return bool(_normalize_steam(sheet_name) & steam_variants)