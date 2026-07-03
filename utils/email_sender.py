"""
utils/email_sender.py
Sends emails via Gmail SMTP.
PNG attachment matches the HTML body style:
  - White background, clean table, generous padding
  - No emoji in cells — text only (W/L/M/A)
  - Medals as text (1,2,3) or rank number
  - Colour-coded cells: green=win, red=loss, amber=miss, grey=abandoned
"""

import smtplib
import io
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.base      import MIMEBase
from email                import encoders
from datetime             import datetime

import streamlit as st


# ── Config ────────────────────────────────────────────────────────────────────

def _cfg():
    cfg = st.secrets.get("email", {})
    return cfg.get("sender",""), cfg.get("app_password",""), cfg.get("recipient","")

def email_configured() -> bool:
    s, p, r = _cfg()
    return bool(s and p and r)


# ── Fonts — DejaVu Sans via matplotlib (fixed, no fallback chain) ────────────

import matplotlib.font_manager as _fm
from matplotlib import rcParams as _rcp

def _setup_font():
    """
    Register DejaVu Sans as the global matplotlib font.
    Called once at import time. matplotlib bundles DejaVu Sans so it is
    always available regardless of OS.
    """
    _rcp["font.family"] = "DejaVu Sans"
    _rcp["pdf.fonttype"] = 42
    _rcp["ps.fonttype"]  = 42

_setup_font()


# ── Colours ───────────────────────────────────────────────────────────────────

WHITE      = (255, 255, 255)
BLACK      = ( 20,  20,  20)
GREY_TEXT  = (100, 100, 100)
GREY_BG    = (245, 246, 248)   # alternating row
HDR_BG     = ( 40,  50,  80)   # dark header
HDR_TEXT   = (255, 255, 255)
GRID       = (210, 213, 220)   # grid lines

WIN_BG     = (209, 240, 215)   # light green
WIN_FG     = ( 14, 110,  36)   # dark green
LOSS_BG    = (252, 215, 215)   # light red
LOSS_FG    = (160,  20,  20)   # dark red
MISS_BG    = (255, 243, 205)   # light amber
MISS_FG    = (140,  80,   0)   # dark amber
ABAND_BG   = (220, 220, 220)   # light grey
ABAND_FG   = (110, 110, 110)   # mid grey
TITLE_FG   = ( 30,  40,  80)
SUB_FG     = ( 80,  90, 110)





# ── PNG table renderer — matplotlib @ 400 DPI ────────────────────────────────

def _render_table_png(title: str, subtitle: str,
                       headers: list[str],
                       rows: list[list],
                       row_styles: list[list],   # list of list of (bg,fg,text) per cell
                       heroes: dict = None,       # leaderboard_heroes() output, optional
                       penalties: list[dict] = None,  # manual penalties, optional
                       ) -> bytes:
    """
    Render a clean table as a PNG using matplotlib at 400 DPI.
    Font: DejaVu Sans (regular + bold).  Colours match the HTML email body.
    If heroes is provided, a highlights section is drawn below the table.
    If penalties is provided, a penalty list is drawn below highlights.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.font_manager import FontProperties

    DPI        = 400

    # Font sizes (points — rendered at 400 DPI so they appear crisp)
    FS_TITLE   = 9
    FS_SUB     = 6.5
    FS_HDR     = 6
    FS_BODY    = 5.5
    FS_FOOT    = 5

    fp_reg  = FontProperties(family="DejaVu Sans", weight="normal", size=FS_BODY)
    fp_bold = FontProperties(family="DejaVu Sans", weight="bold",   size=FS_BODY)
    fp_hdr  = FontProperties(family="DejaVu Sans", weight="bold",   size=FS_HDR)
    fp_title= FontProperties(family="DejaVu Sans", weight="bold",   size=FS_TITLE)
    fp_sub  = FontProperties(family="DejaVu Sans", weight="normal", size=FS_SUB)
    fp_foot = FontProperties(family="DejaVu Sans", weight="normal", size=FS_FOOT)

    n_cols = len(headers)
    n_rows = len(rows)

    # ── Column width estimation (inches) ────────────────────────────────────
    # Use a throw-away figure to measure text widths in display units,
    # then convert to inches.
    fig_tmp, ax_tmp = plt.subplots(1, 1, figsize=(1, 1), dpi=DPI)
    renderer = fig_tmp.canvas.get_renderer()

    def _text_w_in(text: str, fp: FontProperties) -> float:
        """Measure rendered text width in inches."""
        t = ax_tmp.text(0, 0, text, fontproperties=fp)
        bb = t.get_window_extent(renderer=renderer)
        t.remove()
        return bb.width / DPI

    CELL_PAD   = 0.06   # inches padding each side
    MIN_W_RANK = 0.22
    MIN_W_NAME = 0.80
    MIN_W_DATA = 0.38

    col_widths = []
    for ci, h in enumerate(headers):
        w = _text_w_in(h, fp_hdr) + CELL_PAD * 2
        for row, sty in zip(rows, row_styles):
            if ci < len(sty):
                cw = _text_w_in(sty[ci][2], fp_bold if ci <= 1 else fp_reg) + CELL_PAD * 2
                w  = max(w, cw)
        if   ci == 0: w = max(w, MIN_W_RANK)
        elif ci == 1: w = max(w, MIN_W_NAME)
        else:         w = max(w, MIN_W_DATA)
        col_widths.append(w)

    plt.close(fig_tmp)

    # ── Figure dimensions ────────────────────────────────────────────────────
    PAD_OUT    = 0.18   # outer margin inches
    ROW_H      = 0.22   # data / header row height inches
    TITLE_H    = 0.22
    SUB_H      = 0.16
    FOOTER_H   = 0.16
    SEP        = 0.06   # gap between title block and table

    # Highlights block geometry
    HL_LABELS  = ["Win Streak", "Loss Streak", "Most Missed"]
    HL_KEYS    = ["top_win_streak", "top_loss_streak", "top_missed"]
    HLABEL_H   = 0.16
    HL_CARD_H  = 0.32
    HL_SEP     = 0.10
    has_heroes   = bool(heroes)
    has_penalties = bool(penalties)
    hero_block_h  = (HL_SEP + HLABEL_H + HL_CARD_H) if has_heroes else 0.0
    PEN_ROW_H     = 0.18
    PEN_LABEL_H   = 0.16
    PEN_SEP       = 0.08
    pen_block_h   = (PEN_SEP + PEN_LABEL_H + len(penalties) * PEN_ROW_H) if has_penalties else 0.0

    total_w = sum(col_widths) + PAD_OUT * 2
    total_h = (PAD_OUT + TITLE_H + SUB_H + SEP
               + ROW_H              # header
               + n_rows * ROW_H
               + FOOTER_H + hero_block_h + pen_block_h + PAD_OUT)

    fig = plt.figure(figsize=(total_w, total_h), dpi=DPI)
    fig.patch.set_facecolor("white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, total_w)
    ax.set_ylim(0, total_h)
    ax.axis("off")
    ax.invert_yaxis()   # y=0 at top

    def _rgb(t):
        """Convert 0-255 tuple to 0-1 tuple for matplotlib."""
        if t is None: return None
        return tuple(v / 255 for v in t)

    # ── Title & subtitle ────────────────────────────────────────────────────
    y = PAD_OUT
    ax.text(PAD_OUT, y + TITLE_H * 0.72, title,
            fontproperties=fp_title,
            color=_rgb(TITLE_FG), va="baseline")
    y += TITLE_H
    ax.text(PAD_OUT, y + SUB_H * 0.72, subtitle,
            fontproperties=fp_sub,
            color=_rgb(SUB_FG), va="baseline")
    y += SUB_H + SEP

    # ── Header row ──────────────────────────────────────────────────────────
    x = PAD_OUT
    hdr_color = _rgb(HDR_BG)
    for ci, h in enumerate(headers):
        rect = mpatches.FancyBboxPatch(
            (x, y), col_widths[ci], ROW_H,
            boxstyle="square,pad=0", linewidth=0,
            facecolor=hdr_color, zorder=1)
        ax.add_patch(rect)

        # Center rank, left-align rest
        if ci == 0:
            tx = x + col_widths[ci] / 2
            ha = "center"
        else:
            tx = x + CELL_PAD
            ha = "left"
        ax.text(tx, y + ROW_H * 0.62, h,
                fontproperties=fp_hdr,
                color=_rgb(HDR_TEXT), ha=ha, va="baseline", zorder=2)
        x += col_widths[ci]

    # Thin line under header
    ax.axhline(y + ROW_H, xmin=PAD_OUT / total_w,
               xmax=(total_w - PAD_OUT) / total_w,
               color=_rgb(GRID), linewidth=0.4, zorder=3)
    y += ROW_H

    # ── Data rows ────────────────────────────────────────────────────────────
    for ri, (row, sty) in enumerate(zip(rows, row_styles)):
        row_bg = _rgb(GREY_BG) if ri % 2 == 1 else "white"
        # Row background
        bg_rect = mpatches.FancyBboxPatch(
            (PAD_OUT, y), sum(col_widths), ROW_H,
            boxstyle="square,pad=0", linewidth=0,
            facecolor=row_bg, zorder=1)
        ax.add_patch(bg_rect)

        x = PAD_OUT
        for ci, (cell_bg, cell_fg, cell_txt) in enumerate(sty):
            # Text colour only — no cell background (cleaner at high DPI)
            fp = fp_bold if ci <= 1 else fp_reg
            ty = y + ROW_H * 0.62

            # Alignment: center rank, right-align data cols, left-align name
            if ci == 0:
                tx = x + col_widths[ci] / 2
                ha = "center"
            elif ci >= 2:
                tx = x + col_widths[ci] - CELL_PAD
                ha = "right"
            else:
                tx = x + CELL_PAD
                ha = "left"

            ax.text(tx, ty, cell_txt,
                    fontproperties=fp,
                    color=_rgb(cell_fg), ha=ha, va="baseline", zorder=2)
            x += col_widths[ci]

        # Bottom grid line
        ax.axhline(y + ROW_H, xmin=PAD_OUT / total_w,
                   xmax=(total_w - PAD_OUT) / total_w,
                   color=_rgb(GRID), linewidth=0.3, zorder=3)
        y += ROW_H

    # ── Highlights ───────────────────────────────────────────────────────────
    if has_heroes:
        y += HL_SEP
        fp_hl_label = FontProperties(family="DejaVu Sans", weight="bold",   size=5.5)
        fp_hl_name  = FontProperties(family="DejaVu Sans", weight="bold",   size=5.5)
        fp_hl_val   = FontProperties(family="DejaVu Sans", weight="normal", size=5.0)
        ax.text(PAD_OUT, y + HLABEL_H * 0.72, "Highlights",
                fontproperties=fp_hl_label,
                color=_rgb(TITLE_FG), va="baseline")
        y += HLABEL_H

        card_w   = (sum(col_widths) - 0.06) / 3
        card_fgs = [WIN_FG, LOSS_FG, MISS_FG]
        card_bgs = [(209,240,215), (252,215,215), (255,243,205)]

        for ci, (lbl, key) in enumerate(zip(HL_LABELS, HL_KEYS)):
            hero  = (heroes or {}).get(key, {})
            names = hero.get("names", "—")
            value = hero.get("value", 0)
            cx    = PAD_OUT + ci * (card_w + 0.03)
            unit  = "wins" if ci == 0 else ("losses" if ci == 1 else "missed")

            card_rect = mpatches.FancyBboxPatch(
                (cx, y), card_w, HL_CARD_H,
                boxstyle="round,pad=0.01", linewidth=0.5,
                edgecolor=_rgb(card_fgs[ci]),
                facecolor=_rgb(card_bgs[ci]), zorder=1)
            ax.add_patch(card_rect)

            ax.text(cx + 0.05, y + HL_CARD_H * 0.28, lbl,
                    fontproperties=fp_hl_val,
                    color=_rgb(card_fgs[ci]), va="baseline", zorder=2)
            ax.text(cx + 0.05, y + HL_CARD_H * 0.60, names,
                    fontproperties=fp_hl_name,
                    color=_rgb(card_fgs[ci]), va="baseline", zorder=2)
            ax.text(cx + 0.05, y + HL_CARD_H * 0.88, f"{value} {unit}",
                    fontproperties=fp_hl_val,
                    color=_rgb(card_fgs[ci]), va="baseline", zorder=2)
        y += HL_CARD_H

    # ── Penalties ────────────────────────────────────────────────────────────
    if has_penalties:
        y += PEN_SEP
        fp_pen_label = FontProperties(family="DejaVu Sans", weight="bold",   size=5.5)
        fp_pen_body  = FontProperties(family="DejaVu Sans", weight="normal", size=5.0)
        fp_pen_pts   = FontProperties(family="DejaVu Sans", weight="bold",   size=5.0)
        ax.text(PAD_OUT, y + PEN_LABEL_H * 0.72, "Manual Penalties",
                fontproperties=fp_pen_label,
                color=_rgb(TITLE_FG), va="baseline")
        y += PEN_LABEL_H

        for pi, p in enumerate(penalties or []):
            row_bg = _rgb(GREY_BG) if pi % 2 == 1 else "white"
            bg_rect = mpatches.FancyBboxPatch(
                (PAD_OUT, y), sum(col_widths), PEN_ROW_H,
                boxstyle="square,pad=0", linewidth=0,
                facecolor=row_bg, zorder=1)
            ax.add_patch(bg_rect)

            pts_str  = f"-{float(p['points']):.2f}"
            date_str = p.get("created_at", "")[:10]
            reason   = p.get("reason", "")
            name     = p.get("player_name", p.get("user_id", ""))

            ty = y + PEN_ROW_H * 0.65
            col_x = PAD_OUT
            # Name (25% width), Points (15%), Reason (45%), Date (15%)
            total_col_w = sum(col_widths)
            ax.text(col_x,                        ty, name,     fontproperties=fp_pen_body, color=_rgb(BLACK),   va="baseline", zorder=2)
            ax.text(col_x + total_col_w * 0.28,   ty, pts_str,  fontproperties=fp_pen_pts,  color=_rgb(LOSS_FG), va="baseline", zorder=2)
            ax.text(col_x + total_col_w * 0.40,   ty, reason,   fontproperties=fp_pen_body, color=_rgb(BLACK),   va="baseline", zorder=2)
            ax.text(col_x + total_col_w * 0.88,   ty, date_str, fontproperties=fp_pen_body, color=_rgb(GREY_TEXT),va="baseline", zorder=2)

            ax.axhline(y + PEN_ROW_H, xmin=PAD_OUT / total_w,
                       xmax=(total_w - PAD_OUT) / total_w,
                       color=_rgb(GRID), linewidth=0.3, zorder=3)
            y += PEN_ROW_H

    # ── Footer ───────────────────────────────────────────────────────────────
    now = datetime.utcnow().strftime("%d %b %Y  %H:%M  UTC")
    ax.text(PAD_OUT, y + FOOTER_H * 0.65,
            f"SportsPoll  ·  {now}",
            fontproperties=fp_foot,
            color=_rgb(GREY_TEXT), va="baseline")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI,
                facecolor="white", bbox_inches=None)
    plt.close(fig)
    return buf.getvalue()


# ── Poll results ──────────────────────────────────────────────────────────────

def _penalties_html(penalties: list[dict]) -> str:
    """Build an HTML penalties table for the email body."""
    if not penalties:
        return ""
    rows_html = ""
    for p in penalties:
        pts_str  = f"-{float(p['points']):.2f}"
        date_str = p.get("created_at", "")[:10]
        rows_html += (
            f'<tr>'
            f'<td style="padding:7px 10px">{p["player_name"]}</td>'
            f'<td style="padding:7px 10px;color:#a01414;font-weight:700">{pts_str}</td>'
            f'<td style="padding:7px 10px">{p["reason"]}</td>'
            f'<td style="padding:7px 10px;color:#999;font-size:12px">{date_str}</td>'
            f'</tr>'
        )
    return f"""
      <h3 style="color:#1a2850;margin-top:24px">Manual Penalties</h3>
      <table border="1" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;font-size:14px;font-family:Arial,sans-serif">
        <tr style="background:#28324f;color:#fff">
          <th style="padding:8px 10px;text-align:left">Player</th>
          <th style="padding:8px 10px;text-align:left">Points</th>
          <th style="padding:8px 10px;text-align:left">Reason</th>
          <th style="padding:8px 10px;text-align:left">Date</th>
        </tr>{rows_html}
      </table>"""


def send_poll_results(match: dict, votes: list[dict],
                      win_amounts: dict, display_names: dict,
                      tournament_name: str):
    options   = [o.strip() for o in match["options"].split("|") if o.strip()]
    total     = len(votes)
    by_opt    = {opt: [] for opt in options}
    voted_ids = set()
    for v in votes:
        opt = v.get("vote","")
        if opt in by_opt:
            by_opt[opt].append(display_names.get(v["user_id"], v["user_id"]))
        voted_ids.add(v["user_id"])
    no_vote = sorted(display_names[u] for u in display_names
                     if u not in voted_ids)

    # Build PNG table
    headers = ["Option", "Votes", "%", "Win Pts", "Voters"]
    rows, styles = [], []
    for opt in options:
        voters = by_opt[opt]
        count  = len(voters)
        pct    = f"{round(count/total*100)}%" if total else "0%"
        amt    = win_amounts.get(opt, "—")
        names  = ", ".join(voters) if voters else "—"
        amt_bg = WIN_BG if str(amt).startswith("+") else LOSS_BG
        amt_fg = WIN_FG if str(amt).startswith("+") else LOSS_FG
        rows.append([opt, str(count), pct, amt, names])
        styles.append([
            (None, BLACK, opt),
            (None, BLACK, str(count)),
            (None, BLACK, pct),
            (amt_bg, amt_fg, str(amt)),
            (None, GREY_TEXT, names),
        ])
    if no_vote:
        nv = ", ".join(no_vote)
        rows.append(["Did not vote", "—", "—", "—", nv])
        styles.append([
            (MISS_BG, MISS_FG, "Did not vote"),
            (None, BLACK, "—"),
            (None, BLACK, "—"),
            (None, BLACK, "—"),
            (None, GREY_TEXT, nv),
        ])

    title    = f"Voting Results — {match['title']}"
    subtitle = (f"After: {match['match_date']} {match['start_time']} "
                f"{match['timezone'].split('/')[-1]}  ·  {total} votes  ·  {tournament_name}")
    png = _render_table_png(title, subtitle, headers, rows, styles)

    # HTML body
    rows_html = ""
    for opt in options:
        voters = by_opt[opt]
        count  = len(voters)
        pct    = round(count/total*100) if total else 0
        amt    = win_amounts.get(opt, "—")
        names  = ", ".join(voters) if voters else "—"
        colour = "#16a34a" if str(amt).startswith("+") else "#dc2626"
        rows_html += f"""<tr>
          <td>{opt}</td><td>{count}</td><td>{pct}%</td>
          <td style="color:{colour};font-weight:700">{amt}</td>
          <td style="color:#555">{names}</td>
        </tr>"""
    if no_vote:
        rows_html += (f'<tr><td colspan="5" style="color:#d97706">'
                      f'<b>Did not vote:</b> {", ".join(no_vote)}</td></tr>')



    html = f"""<!DOCTYPE html><html><body
      style="font-family:Arial,sans-serif;background:#fff;padding:24px;color:#111">
      <h2 style="color:#1a2850">Voting Results — {match['title']}</h2>
      <p><b>Tournament:</b> {tournament_name}<br>
         <b>Date:</b> {match['match_date']} {match['start_time']}
         {match['timezone'].split('/')[-1]}<br>
         <b>Total votes:</b> {total}</p>
      <table border="1" cellpadding="10" cellspacing="0"
             style="border-collapse:collapse;width:100%;font-size:14px">
        <tr style="background:#28324f;color:#fff">
          <th>Option</th><th>Votes</th><th>%</th>
          <th>Win Points</th><th>Voters</th>
        </tr>{rows_html}
      </table>
      <p style="font-size:11px;color:#aaa;margin-top:16px">
        See attached PNG for shareable version.</p>
    </body></html>"""

    _send(subject  = f"[{tournament_name}] {match['title']} — Voting Results",
          html_body= html, png_bytes=png,
          filename = f"poll_{match['match_id']}.png")


# ── Leaderboard ───────────────────────────────────────────────────────────────

def send_leaderboard(match: dict, result: str,
                     tournament_id: str,
                     tournament_name: str):
    """
    Build and send the leaderboard email.
    All data assembly delegated to leaderboard_builder.build_lb_data().
    Email columns show the last 5 completed matches.
    """
    from data.leaderboard_builder import build_lb_data, cell_text, cell_colours

    data          = build_lb_data(tournament_id, last_n_matches=5)
    rows          = data["rows"]
    col_match_ids = data["col_match_ids"]
    labels        = data["labels"]
    col_totals    = data["col_totals"]
    grand_total   = data["grand_total"]
    bank          = data["bank"]
    heroes        = data["heroes"]
    penalties     = data.get("penalties", [])
    penalty_total = data.get("penalty_total", 0.0)

    bank_str = f"+{bank:.2f}" if bank >= 0 else f"{bank:.2f}"
    gt_str   = f"+{grand_total:.2f}" if grand_total >= 0 else f"{grand_total:.2f}"
    m_labels = [labels[mid] for mid in col_match_ids]
    medals   = ["1", "2", "3"]

    # ── Build PNG rows & styles ───────────────────────────────────────────────
    png_rows, png_styles = [], []

    for i, row in enumerate(rows):
        rank    = medals[i] if i < 3 else str(i + 1)
        name    = str(row.get("name", ""))
        pts     = float(row.get("total_points", 0))
        winp    = float(row.get("win_pct", 0))
        miss    = int(row.get("missed", 0))
        pts_str = f"+{pts:.2f}" if pts >= 0 else f"{pts:.2f}"
        pts_fg  = WIN_FG  if pts >= 0 else LOSS_FG
        miss_fg = MISS_FG if miss > 0 else BLACK

        row_cells  = [rank, name, pts_str, f"{winp:.0f}%", str(miss)]
        row_styles = [
            (None, BLACK,  rank),
            (None, BLACK,  name),
            (None, pts_fg,         pts_str),
            (None, GREY_TEXT,   f"{winp:.0f}%"),
            (None, miss_fg,        str(miss)),
        ]

        for mid in col_match_ids:
            val      = row.get(mid)
            txt      = cell_text(val)
            fg_hex, _= cell_colours(val)
            # Convert hex → RGB tuple for matplotlib
            fg_rgb   = tuple(int(fg_hex.lstrip("#")[i:i+2], 16) for i in (0,2,4))
            row_cells.append(txt)
            row_styles.append((None, fg_rgb, txt))

        png_rows.append(row_cells)
        png_styles.append(row_styles)

    # Total row
    tc_cells  = ["—", "Total", gt_str, "", ""]
    tc_fg     = WIN_FG if grand_total >= 0 else LOSS_FG
    tc_styles = [
        (None, BLACK, "—"),
        (None, BLACK, "Total"),
        (None, tc_fg,         gt_str),
        (None, BLACK, ""),
        (None, BLACK, ""),
    ]
    for mid in col_match_ids:
        t     = col_totals.get(mid, 0.0)
        v     = f"+{t:.2f}" if t > 0 else (f"{t:.2f}" if t < 0 else "0")
        fg    = WIN_FG if t > 0 else (LOSS_FG if t < 0 else GREY_TEXT)
        tc_cells.append(v)
        tc_styles.append((None, fg, v))
    png_rows.append(tc_cells)
    png_styles.append(tc_styles)

    headers = ["#", "Player", "Points", "Win%", "Missed"] + m_labels
    title   = f"Leaderboard — {tournament_name}"
    sub     = f"After: {match['title']}  ·  Result: {result} Won  ·  Bank: {bank_str} pts"
    png     = _render_table_png(title, sub, headers, png_rows, png_styles,
                             heroes, penalties)

    # ── HTML body ─────────────────────────────────────────────────────────────
    medal_icons = ["🥇", "🥈", "🥉"]
    m_hdrs      = "".join(f"<th>{lbl}</th>" for lbl in m_labels)
    rows_html   = ""

    for i, row in enumerate(rows):
        rank    = medal_icons[i] if i < 3 else str(i + 1)
        name    = row.get("name", "")
        pts     = float(row.get("total_points", 0))
        winp    = float(row.get("win_pct", 0))
        miss    = int(row.get("missed", 0))
        pts_c   = "#16a34a" if pts >= 0 else "#dc2626"
        pts_s   = f"+{pts:.2f}" if pts >= 0 else f"{pts:.2f}"

        mcells = ""
        for mid in col_match_ids:
            val      = row.get(mid)
            txt      = cell_text(val)
            fg, bg   = cell_colours(val)
            bg_style = f"background:{bg};" if bg else ""
            mcells  += f'<td style="{bg_style}color:{fg}">{txt}</td>'

        rows_html += f"""<tr>
          <td style="text-align:center">{rank}</td>
          <td><b>{name}</b></td>
          <td style="color:{pts_c};font-weight:700">{pts_s}</td>
          <td>{winp:.0f}%</td>
          <td>{miss}</td>{mcells}</tr>"""

    _th  = "padding:8px 10px;font-weight:700;border-top:2px solid #28324f;background:#f0f4ff"
    _gc  = "#0e6e24" if grand_total >= 0 else "#a01414"
    _bc  = "#0e6e24" if bank >= 0 else "#a01414"
    total_row = "<tr>"
    total_row += f'<td style="{_th};text-align:center">—</td>'
    total_row += f'<td style="{_th}"><b>Total</b></td>'
    total_row += f'<td style="{_th};color:{_gc}"><b>{gt_str}</b></td>'
    total_row += f'<td style="{_th}"></td><td style="{_th}"></td>'
    for mid in col_match_ids:
        t  = col_totals.get(mid, 0.0)
        c  = "#0e6e24" if t > 0 else ("#a01414" if t < 0 else "#555")
        v  = f"+{t:.2f}" if t > 0 else (f"{t:.2f}" if t < 0 else "0")
        total_row += f'<td style="{_th};color:{c}"><b>{v}</b></td>'
    total_row += "</tr>"

    html = f"""<!DOCTYPE html><html><body
      style="font-family:Arial,sans-serif;background:#fff;padding:24px;color:#111">
      <h2 style="color:#1a2850">Leaderboard — {tournament_name}</h2>
      <p><b>After:</b> {match['title']}<br><b>Result:</b> {result} Won</p>
      <table border="1" cellpadding="10" cellspacing="0"
             style="border-collapse:collapse;width:100%;font-size:14px">
        <tr style="background:#28324f;color:#fff">
          <th>#</th><th>Player</th><th>Points</th>
          <th>Win%</th><th>Missed</th>{m_hdrs}
        </tr>{rows_html}{total_row}
      </table>
      <p style="margin-top:8px">
        🏦 <b>Bank:</b>
        <span style="color:{_bc};font-weight:700">{bank_str} pts</span>
      </p>
      <p style="font-size:12px;color:#aaa;margin-top:8px">
        Last {len(col_match_ids)} completed matches (latest first).<br>
        See attached PNG for shareable version.</p>
    {_penalties_html(penalties)}
    </body></html>"""

    _send(subject   = f"[{tournament_name}] Leaderboard after {match['title']}",
          html_body = html, png_bytes=png,
          filename  = f"leaderboard_{match['match_id']}.png")


# ── Send ──────────────────────────────────────────────────────────────────────

def _send(subject: str, html_body: str,
          png_bytes: bytes = None, filename: str = "table.png"):
    sender, app_password, recipient = _cfg()
    if not all([sender, app_password, recipient]):
        raise ValueError("Email not configured — add [email] to secrets.toml")

    msg            = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"SportsPoll <{sender}>"
    msg["To"]      = recipient
    msg.attach(MIMEText(html_body, "html"))

    if png_bytes:
        part = MIMEBase("image", "png")
        part.set_payload(png_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition",
                        "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())


# ── Result email orchestration ───────────────────────────────────────────────

def send_result_emails(match: dict, result: str,
                       tournament_id: str, point_records: list[dict]):
    """
    Build and send both emails after a result is saved:
      1. Poll results (votes + calculated win amounts)
      2. Leaderboard (full lb + last 5 match columns)

    Raises on failure — framework-agnostic, callers decide their own
    UI/response feedback (Streamlit shows a warning/toast; the API returns
    an email_error field instead of failing the request).
    """
    from data.db import get_votes, get_all_users, get_display_name, get_tournament

    tournament    = get_tournament(tournament_id) or {}
    t_name        = tournament.get("name", tournament_id)
    options       = [o.strip() for o in match["options"].split("|") if o.strip()]
    votes         = get_votes(match_id=match["match_id"])
    all_users     = get_all_users()
    display_names = {u["user_id"]: get_display_name(u["user_id"])
                     for u in all_users}

    # ── Win amounts per option ────────────────────────────────────────────────
    winner_pts = next(
        (float(r["total_points"]) for r in point_records
         if r.get("total_points", 0) > 0), 0.0
    )
    win_amounts = {}
    for opt in options:
        if opt == result:
            win_amounts[opt] = f"+{winner_pts:.2f} pts"
        else:
            win_amounts[opt] = "−1 pt"

    send_poll_results(match, votes, win_amounts, display_names, t_name)
    send_leaderboard(match, result, tournament_id, t_name)
