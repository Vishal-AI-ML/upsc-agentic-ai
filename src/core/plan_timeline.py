"""Pure, deterministic study-plan timeline helpers (no LLM / heavy deps).

The planner agent computes attempt-year, months-left and a timeline message
inline while streaming. That logic is CODE-derived (not model output), so it can
live in a pure, offline-testable helper and be exposed as structured
StudyPlanMeta. `dateutil` is optional (guarded) so this stays import-light.
"""
import re
from datetime import datetime

from src.schemas import StudyPlanMeta

_YEAR_RE = re.compile(r"20\d\d")


def parse_attempt_year(goal, today=None):
    today = today or datetime.now()
    m = _YEAR_RE.search(goal or "")
    return int(m.group()) if m else today.year + 1


def _months_from_year(attempt_year, today):
    # Heuristic: assume prelims ~June of the attempt year.
    return max(0, (attempt_year - today.year) * 12 + (6 - today.month))


def _months_from_date(prelims_dt, today):
    return max(0, (prelims_dt.year - today.year) * 12 + (prelims_dt.month - today.month))


# Offline-safe date parsing. `dateutil` is optional (not a hard dependency), so
# we fall back to a set of common explicit formats when it is unavailable. This
# keeps the helper deterministic in the offline CI gate.
_DATE_FORMATS = (
    "%d %B %Y",
    "%d %b %Y",
    "%d %B, %Y",
    "%d %b, %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
)


def _parse_live_date(live_date):
    """Parse a human date string into a datetime, or return None.

    Tries `dateutil` when present, otherwise a list of explicit formats so the
    result is identical with or without the optional dependency.
    """
    if not live_date:
        return None
    try:
        from dateutil import parser as dateparser

        return dateparser.parse(live_date)
    except Exception:
        pass
    text = live_date.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def timeline_message(months_left):
    if months_left == 0:
        return "Prelims is this month. Shift focus entirely to revision and mocks."
    if months_left <= 2:
        return "CRITICAL — under 2 months. Stop new material. Only revision and mocks."
    if months_left <= 4:
        return "Under 4 months. High-yield topics only. 3 mocks per week minimum."
    if months_left <= 6:
        return "Under 6 months. Intensive — cover all high-priority topics with daily testing."
    if months_left <= 12:
        return "Around 1 year. Balanced prep — complete syllabus with regular revision."
    return "1+ years. Build unshakeable base. Quality over speed."


def compute_plan_timeline(goal, *, today=None, live_date=None):
    """Return StudyPlanMeta. Uses parsed `live_date` when available, else a
    June-of-attempt-year heuristic. Mirrors planner.generate_plan's inline logic."""
    today = today or datetime.now()
    attempt_year = parse_attempt_year(goal, today)
    months_left = None
    if live_date:
        parsed = _parse_live_date(live_date)
        if parsed is not None:
            months_left = _months_from_date(parsed, today)
    if months_left is None:
        months_left = _months_from_year(attempt_year, today)
    return StudyPlanMeta(
        attempt_year=attempt_year,
        months_left=months_left,
        timeline_msg=timeline_message(months_left),
        prelims_date=live_date or None,
    )
