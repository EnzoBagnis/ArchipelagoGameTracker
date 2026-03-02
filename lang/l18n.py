"""
i18n.py — Internationalisation pour Archipelago Tracker
--------------------------------------------------------
Usage :
    from i18n import t, set_lang, available_langs

    set_lang("en")          # charge locales/en.yaml
    t("btn_check")          # → "⟳  Check for updates"
    t("count_label", n=42)  # → "42 games"
"""

import os
import re
import sys

# PyYAML est la seule dépendance externe.
# Si absent, on tombe sur le parser minimaliste intégré ci-dessous.
try:
    import yaml as _yaml
    def _load_yaml(path):
        with open(path, "r", encoding="utf-8") as f:
            return _yaml.safe_load(f)
except ImportError:
    # Fallback : parser YAML ultra-simple (clé: valeur sur une ligne,
    # gère les scalaires entre guillemets et les block scalars ">").
    def _load_yaml(path):
        data = {}
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            # Skip comments and blanks
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                i += 1
                continue
            m = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)', line)
            if not m:
                i += 1
                continue
            key, rest = m.group(1), m.group(2).strip()
            if rest == ">":
                # Block scalar: collect following indented lines
                i += 1
                parts = []
                while i < len(lines) and (lines[i].startswith("  ") or lines[i].strip() == ""):
                    parts.append(lines[i].strip())
                    i += 1
                data[key] = " ".join(p for p in parts if p)
            elif rest.startswith('"') and rest.endswith('"'):
                data[key] = rest[1:-1]
            elif rest.startswith("'") and rest.endswith("'"):
                data[key] = rest[1:-1]
            else:
                data[key] = rest
                i += 1
        return data


# ── Internal state ─────────────────────────────────────────────────────────────
# Determine where the locale files are located. When running from a
# PyInstaller bundle the files are extracted to sys._MEIPASS, so we need to
# take that into account; otherwise we resolve relative to this module file.
if getattr(sys, "frozen", False):
    _LOCALES_DIR = os.path.join(sys._MEIPASS, "lang")
else:
    _LOCALES_DIR = os.path.dirname(__file__)

_strings: dict = {}
_lang_code: str = "fr"


def _locale_path(code: str) -> str:
    return os.path.join(_LOCALES_DIR, f"{code}.yaml")


def available_langs() -> dict[str, str]:
    """Return {code: lang_name} for every .yaml file in locales/."""
    langs = {}
    if not os.path.isdir(_LOCALES_DIR):
        return langs
    for fname in sorted(os.listdir(_LOCALES_DIR)):
        if not fname.endswith(".yaml"):
            continue
        code = fname[:-5]
        try:
            data = _load_yaml(_locale_path(code))
            langs[code] = data.get("lang_name", code)
        except Exception:
            langs[code] = code
    return langs


def set_lang(code: str) -> None:
    """Load the locale file for `code` (e.g. 'fr', 'en')."""
    global _strings, _lang_code
    path = _locale_path(code)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Locale file not found: {path}")
    _strings = _load_yaml(path)
    _lang_code = code


def current_lang() -> str:
    return _lang_code


def t(key: str, **kwargs) -> str:
    """
    Translate `key`, substituting any {placeholder} with kwargs.

    Example:
        t("count_label", n=42)   # "42 games"  /  "42 jeux"
        t("last_check_label", ts="2025-01-01 12:00")
    """
    raw = _strings.get(key)
    if raw is None:
        # Return the key itself so missing translations are visible
        return f"[{key}]"
    if kwargs:
        try:
            return raw.format(**kwargs)
        except (KeyError, ValueError):
            return raw
    return raw


# ── Bootstrap: load default locale on import ───────────────────────────────────
def _init():
    from cache import load_settings
    try:
        code = load_settings().get("lang", "fr")
    except Exception:
        code = "fr"
    path = _locale_path(code)
    if not os.path.exists(path):
        code = "fr"
    try:
        set_lang(code)
    except Exception:
        pass

_init()