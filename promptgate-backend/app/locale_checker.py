"""
i18n correctness checks using Babel locale data.

run_locale_checks(output, locale) returns a list of (check_type, passed, details)
tuples. Checks are driven by Babel's locale data (text direction, decimal/group
symbols), not hardcoded per-locale regex — adding a new locale to
SUPPORTED_LOCALES doesn't require new check logic, just Babel locale data
(which Babel already ships for hundreds of locales).
"""

from __future__ import annotations

import re
from typing import Optional

from babel import Locale
from babel.numbers import format_decimal

# English month names — detects Western/English date formatting leaking into
# non-English locale output.
#
# No \b word-boundary here: Python's re module treats Han/Hiragana/Katakana
# characters as \w, so there is no boundary between e.g. "は" and "J" in
# "会議はJune 20" — \b would silently fail to match across the CJK/Latin
# transition, which is exactly the case this check exists to catch. Instead,
# match case-sensitively (real English dates capitalize months) with a
# negative lookahead so "June" doesn't match inside "Juneau".
#
# Known limitation: German "April" and "August" are spelled identically to
# their English counterparts and won't be flagged as foreign. Acceptable for
# a portfolio-scale i18n gate, not a full date parser.
_ENGLISH_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_ENGLISH_MONTH_RE = re.compile(
    r"(?:" + "|".join(_ENGLISH_MONTHS) + r")(?![a-zA-Z])"
)

# A run of 4+ raw digits with no separator indicates a number >=1000 that
# should have been grouped but wasn't — regardless of which symbol the
# locale uses for grouping (comma, period, or narrow no-break space). Any
# legitimate grouping separator breaks the digit run, so this stays correct
# across locales without per-locale regex.
#
# Boundaries are digit-adjacency lookarounds, not \b: \b depends on Python's
# \w, which treats CJK characters as word characters too. A number
# immediately followed by a CJK character (e.g. "1234.56円", no space) would
# never hit a trailing \b boundary and the match would silently fail right
# on the case this check exists to catch. Lookarounds that only check for
# adjacent digits sidestep the CJK/\w collision entirely.
#
# Bare 4-digit integers in a plausible calendar-year range are excluded —
# years are conventionally never grouped (nobody writes "2,026"), so without
# this exclusion every mock containing a year would false-positive.
_UNGROUPED_NUMBER_RE = re.compile(r"(?<!\d)\d{4,}(?:[.,]\d+)?(?!\d)")
_YEAR_RANGE = range(1000, 3000)

# Explicit RTL bidi control marks
_RTL_MARKS = ("\u200F", "\u202B", "؜")


def _to_babel_locale(locale: str) -> str:
    return locale.replace("-", "_")


def check_date_format(output: str, locale: str) -> tuple[bool, str]:
    """Flag English month names appearing in non-English-locale output."""
    if locale == "en-US":
        return True, "en-US expects English date format"

    match = _ENGLISH_MONTH_RE.search(output)
    if match:
        return False, f"English month name '{match.group()}' found in {locale} output"
    return True, "no English month name detected"


def check_number_format(output: str, locale: str) -> tuple[bool, str]:
    """Flag numbers >=1000 with no thousands grouping separator at all (years excluded)."""
    for match in _UNGROUPED_NUMBER_RE.finditer(output):
        raw = match.group()

        if re.fullmatch(r"\d{4}", raw) and int(raw) in _YEAR_RANGE:
            continue  # plausible calendar year — not a grouping defect

        try:
            value = float(raw.replace(",", "."))
            example = format_decimal(value, locale=_to_babel_locale(locale))
        except Exception:
            example = "(could not compute example)"
        return False, f"ungrouped number '{raw}' found; expected grouping like '{example}'"

    return True, "no ungrouped numbers >=1000 detected (years excluded)"


def check_rtl(output: str, locale: str) -> Optional[tuple[bool, str]]:
    """
    Check for RTL control marks. Returns None if the locale isn't RTL
    (check not applicable — caller should not write a row for it).
    """
    babel_locale = Locale.parse(_to_babel_locale(locale))
    if babel_locale.text_direction != "rtl":
        return None

    if any(mark in output for mark in _RTL_MARKS):
        return True, "RTL control mark present"
    return False, "no RTL control mark found in RTL-locale output"


def run_locale_checks(output: str, locale: str) -> list[tuple[str, bool, str]]:
    """
    Run all applicable checks for this locale.
    Returns a list of (check_type, passed, details).
    RTL check is only included for locales where Babel reports text_direction='rtl'.
    """
    results: list[tuple[str, bool, str]] = []

    passed, details = check_date_format(output, locale)
    results.append(("date_format", passed, details))

    passed, details = check_number_format(output, locale)
    results.append(("number_format", passed, details))

    rtl_result = check_rtl(output, locale)
    if rtl_result is not None:
        passed, details = rtl_result
        results.append(("rtl", passed, details))

    return results
