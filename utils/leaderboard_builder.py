"""
data/leaderboard_builder.py
Single source of truth for leaderboard data assembly.

build_lb_data() returns a structured dict consumed by:
  - pages/leaderboard.py   (HTML table via st.html)
  - utils/email_sender.py  (PNG attachment + HTML email body)

Renderers never build their own rows, totals, labels or colour logic —
they call build_lb_data() and use what it returns.
"""

from __future__ import annotations
import re


# ── Label formatting ──────────────────────────────────────────────────────────

def match_label(match_id: str) -> str:
    """Canonical match label: 'M:1', 'M:22', etc."""
    m = re.search(r'M0*(\d+)', match_id, re.IGNORECASE)
    if m: return f"M:{m.group(1)}"
    m = re.search(r'(\d+)$', match_id)
    if m: return f"M:{int(m.group(1))}"
    return match_id[-4:]


# ── Cell value & colour ───────────────────────────────────────────────────────
#
# cell_text(val)  → display string  e.g. "+2.50", "M", "Q", "A", "—"
# cell_colours(val) → (fg_hex, bg_hex|None)
#
# These are the single source of truth used by all renderers.
# HTML renderer uses bg_hex for cell backgrounds.
# PNG renderer uses fg for text colour only (no cell backgrounds).

_COLOURS = {
    "win" : ("#0e6e24", "#d1f0d7"),
    "loss": ("#a01414", "#fcd7d7"),
    "miss": ("#8c5500", "#fff3cd"),
    "aband":("#777777", "#e0e0e0"),
    "quit" :("#5a3e8a", "#e8e0f0"),
    "neu"  :("#555555", None),
    "black":("#111111", None),
}

# RGB tuples for matplotlib (email_sender uses these directly)
COLOURS_RGB = {
    "win_fg" : (14, 110, 36),   "win_bg" : (209, 240, 215),
    "loss_fg": (160,  20, 20),  "loss_bg": (252, 215, 215),
    "miss_fg": (140,  80,  0),  "miss_bg": (255, 243, 205),
    "aband_fg":(110,110,110),   "aband_bg":(220, 220, 220),
    "quit_fg" :( 90, 62,138),   "quit_bg" :(232, 224, 240),
    "black"   :( 20, 20, 20),
    "grey"    :(100,100,100),
    "title_fg":( 30, 40, 80),
    "sub_fg"  :( 80, 90,110),
    "hdr_bg"  :( 40, 50, 80),
    "hdr_text":(255,255,255),
    "grid"    :(210,213,220),
    "grey_bg" :(245,246,248),
}


def cell_text(val) -> str:
    """Canonical display string for a match-cell value."""
    if val is None or val == "":
        return "—"
    if val == "A":
        return "A"
    if val == "Q":
        return "Q"
    if val in ("miss", "M"):
        return "M"
    if isinstance(val, str) and val.startswith("−"):
        return f"-{val[1:]}"
    try:
        f = float(val)
        if f > 0:  return f"+{f:.2f}"
        if f < 0:  return f"{f:.2f}"
        return "0"
    except Exception:
        return str(val)


def cell_colours(val) -> tuple[str, str | None]:
    """Return (fg_hex, bg_hex|None) for a match-cell value."""
    if val is None or val == "":
        return _COLOURS["neu"]
    if val == "A":
        return _COLOURS["aband"]
    if val == "Q":
        return _COLOURS["quit"]
    if val in ("miss", "M"):
        return _COLOURS["miss"]
    if isinstance(val, str) and val.startswith("−"):
        return _COLOURS["loss"]
    try:
        f = float(val)
        if f > 0:  return _COLOURS["win"]
        if f < 0:  return _COLOURS["loss"]
        return _COLOURS["neu"]
    except Exception:
        return _COLOURS["black"]


def cell_num(val) -> float:
    """Extract numeric value from a cell — for totals row calculation."""
    if val is None or val in ("", "A", "miss", "M", "Q"):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        try:
            return float(val.replace("−", "-").replace("–", "-"))
        except ValueError:
            return 0.0
    return 0.0


# ── Main builder ──────────────────────────────────────────────────────────────

def build_lb_data(
    tournament_id: str,
    last_n_matches: int | None = None,   # None = all matches; 5 = last 5 for email
) -> dict:
    """
    Assemble all leaderboard data for a tournament.

    Parameters
    ----------
    tournament_id
        The tournament to build data for.
    last_n_matches
        If set, the match columns are limited to the most recent N matches.
        Rows and totals always cover the full tournament; only the column
        display is scoped.  Pass 5 for the email attachment, None for the
        full leaderboard page.

    Returns
    -------
    dict with keys:
        rows          list[dict]   leaderboard rows sorted by points desc
        matches_asc   list[dict]   completed+abandoned matches, oldest first
        match_ids_desc list[str]   all match IDs, latest first (full set)
        col_match_ids list[str]    match IDs used as table columns (may be subset)
        labels        dict         match_id → "M:1" label
        col_totals    dict         match_id → float
        grand_total   float
        bank          float        -grand_total
        heroes        dict         leaderboard_heroes() output
    """
    from data.db      import get_matches, get_points, get_all_users
    from utils.streaks import build_leaderboard, leaderboard_heroes

    matches = [
        m for m in get_matches(tournament_id=tournament_id)
        if m["status"] in ("completed", "abandoned")
    ]
    matches_asc    = sorted(matches, key=lambda m: m["match_date"] + " " + m["start_time"])
    match_ids_desc = [m["match_id"] for m in reversed(matches_asc)]

    points = get_points(tournament_id=tournament_id)
    users  = get_all_users()

    rows = build_leaderboard(points, matches_asc, match_ids_desc, users)

    # Column scope
    if last_n_matches is not None:
        col_match_ids = match_ids_desc[:last_n_matches]
    else:
        col_match_ids = match_ids_desc

    labels = {mid: match_label(mid) for mid in match_ids_desc}

    col_totals  = {mid: sum(cell_num(r.get(mid)) for r in rows)
                   for mid in col_match_ids}
    grand_total = round(sum(float(r.get("total_points", 0)) for r in rows), 3)
    bank        = round(-grand_total, 3)

    heroes = leaderboard_heroes(rows)

    return {
        "rows"          : rows,
        "matches_asc"   : matches_asc,
        "match_ids_desc": match_ids_desc,
        "col_match_ids" : col_match_ids,
        "labels"        : labels,
        "col_totals"    : col_totals,
        "grand_total"   : grand_total,
        "bank"          : bank,
        "heroes"        : heroes,
    }
