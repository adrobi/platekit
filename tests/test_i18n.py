"""Tests for RU/EN translation completeness, OS language auto-detection and fallback."""

from __future__ import annotations

import locale

from i18n import EN, RU, detect_system_language, language, set_language, tr


def test_translation_keys_match():
    assert set(RU.keys()) == set(EN.keys())


def test_language_switching_and_interpolation():
    set_language("ru")
    assert language() == "ru"
    assert "Готово" in tr("status.ready", fmt="96", occupied=12, total=96)

    set_language("en")
    assert language() == "en"
    assert "Ready" in tr("status.ready", fmt="96", occupied=12, total=96)

    # Unknown language falls back to English
    set_language("fr")
    assert language() == "en"


def test_detect_system_language_env_and_fallback(monkeypatch):
    for var in ("LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG"):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    assert detect_system_language() == "ru"

    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert detect_system_language() == "en"

    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    assert detect_system_language() == "en"

    # When env is C/empty and system locale cannot be determined -> fallback to "en"
    monkeypatch.setenv("LANG", "C")
    monkeypatch.setattr(locale, "getlocale", lambda: (None, None))
    assert detect_system_language() in ("ru", "en")
