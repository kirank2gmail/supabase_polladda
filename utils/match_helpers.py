"""
utils/match_helpers.py — pure match-creation helpers shared by admin/dashboard.py
(Streamlit) and api/routers/matches.py (FastAPI). No storage access; safe to
call from either surface.
"""

import re


def parse_time(raw: str) -> str:
    """
    Parse time string flexibly, defaulting missing mm/ss to 00.
    Accepts: "19", "19:30", "19:30:00", "7pm", "7:30pm"
    Returns: "HH:MM" always.
    """
    raw = str(raw).strip()
    if not raw:
        return "00:00"

    # Handle am/pm
    pm = raw.lower().endswith("pm")
    am = raw.lower().endswith("am")
    raw_clean = re.sub(r'[aApP][mM]$', '', raw).strip()

    parts = re.split(r'[:.]', raw_clean)
    try:
        hh = int(parts[0]) if parts else 0
        mm = int(parts[1]) if len(parts) > 1 else 0
        # ss ignored — we only need HH:MM
    except ValueError:
        return "00:00"

    if pm and hh != 12: hh += 12
    if am and hh == 12: hh  = 0
    hh = min(hh, 23)
    mm = min(mm, 59)
    return f"{hh:02d}:{mm:02d}"


def options_from_title(title: str) -> str:
    if not title.strip():
        return ""
    parts = re.split(r'\s+(?:vs\.?|v\.?)\s+|\s*/\s*|\s+-\s+',
                     title.strip(), flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    return "|".join(parts) if len(parts) >= 2 else ""


def validate_options(s: str) -> tuple[bool, str]:
    parts = [o.strip() for o in s.split("|") if o.strip()]
    if len(parts) < 2:
        return False, "At least 2 options required, pipe-separated e.g. `SRH|RCB`"
    return True, ""
