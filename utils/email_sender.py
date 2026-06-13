"""
utils/email_sender.py
Sends emails via Gmail SMTP.
Each email has:
  - A plain HTML body (simple, readable in any client)
  - A PNG attachment of the same table rendered with Pillow
    (white background, black text, Segoe UI font, colour-coded cells)
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


# ── Pillow image rendering ────────────────────────────────────────────────────

def _get_font(size: int, bold: bool = False):
    """Load Segoe UI if available, fall back to DejaVu then default."""
    from PIL import ImageFont
    candidates = []
    if bold:
        candidates = [
            "C:/Windows/Fonts/segoeuib.ttf",           # Windows
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    else:
        candidates = [
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


# Cell background colours (RGB) — white background scheme
CELL_WIN  = (220, 255, 220)   # light green
CELL_LOSS = (255, 220, 220)   # light red
CELL_MISS = (255, 245, 210)   # light amber
CELL_NONE = (255, 255, 255)   # white
HDR_BG    = (30,  40,  80)    # dark blue header
HDR_FG    = (255, 255, 255)   # white header text
TEXT_BLK  = (20,  20,  20)    # near-black text
TEXT_WIN  = (20,  120,  40)   # dark green
TEXT_LOSS = (180,  20,  20)   # dark red
TEXT_MISS = (160,  90,   0)   # dark amber
ROW_ALT   = (245, 247, 252)   # very light blue-grey for alternating rows


def _text_colour(cell_bg: tuple) -> tuple:
    """Return appropriate text colour for a given cell background."""
    if cell_bg == CELL_WIN:   return TEXT_WIN
    if cell_bg == CELL_LOSS:  return TEXT_LOSS
    if cell_bg == CELL_MISS:  return TEXT_MISS
    return TEXT_BLK


def _cell_bg(val) -> tuple:
    """Determine cell background from raw value."""
    if val is None or val == "":  return CELL_NONE
    if val == "miss":             return CELL_MISS
    if isinstance(val, str) and val.startswith("−"): return CELL_LOSS
    try:
        f = float(val)
        if f > 0: return CELL_WIN
        if f < 0: return CELL_LOSS
    except Exception:
        pass
    return CELL_NONE


def _fmt_val(val) -> str:
    if val is None or val == "": return "—"
    if val == "miss":            return "⚠ miss"
    if isinstance(val, str) and val.startswith("−"):
        return f"-{val[1:]}"
    try:
        f = float(val)
        if f > 0:  return f"+{f:.2f}"
        if f < 0:  return f"{f:.2f}"
        return "0"
    except Exception:
        return str(val)


def _render_table_png(headers: list[str], rows: list[list],
                       row_cell_bgs: list[list],
                       title: str, subtitle: str) -> bytes:
    """
    Render a table as a PNG image.
    headers        — list of column header strings
    rows           — list of row value lists (already formatted strings)
    row_cell_bgs   — parallel list of RGB tuples for each cell background
    """
    from PIL import Image, ImageDraw

    PADDING    = 20
    ROW_H      = 32
    HDR_ROW_H  = 36
    TITLE_H    = 50
    SUBTITLE_H = 28
    FOOTER_H   = 28

    font_hdr   = _get_font(14, bold=True)
    font_body  = _get_font(13, bold=False)
    font_title = _get_font(17, bold=True)
    font_sub   = _get_font(13, bold=False)

    # Measure column widths
    dummy = Image.new("RGB", (1, 1))
    dc    = ImageDraw.Draw(dummy)

    col_widths = []
    for ci, h in enumerate(headers):
        w = dc.textlength(h, font=font_hdr) + 24
        for row in rows:
            if ci < len(row):
                cw = dc.textlength(str(row[ci]), font=font_body) + 24
                w  = max(w, cw)
        col_widths.append(max(int(w), 60))

    total_w = sum(col_widths) + PADDING * 2
    total_h = (TITLE_H + SUBTITLE_H + HDR_ROW_H +
               len(rows) * ROW_H + FOOTER_H + PADDING * 2)

    img  = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Title
    y = PADDING
    draw.text((PADDING, y), title,
              font=font_title, fill=(20, 40, 80))
    y += TITLE_H

    draw.text((PADDING, y), subtitle,
              font=font_sub, fill=(100, 100, 120))
    y += SUBTITLE_H

    # Header row
    x = PADDING
    draw.rectangle([PADDING, y, total_w - PADDING, y + HDR_ROW_H], fill=HDR_BG)
    for ci, h in enumerate(headers):
        draw.text((x + 8, y + 10), h, font=font_hdr, fill=HDR_FG)
        x += col_widths[ci]
    y += HDR_ROW_H

    # Data rows
    for ri, (row, bgs) in enumerate(zip(rows, row_cell_bgs)):
        row_bg = ROW_ALT if ri % 2 == 1 else (255, 255, 255)
        draw.rectangle([PADDING, y, total_w - PADDING, y + ROW_H], fill=row_bg)

        x = PADDING
        for ci, (cell_val, cell_bg) in enumerate(zip(row, bgs)):
            # Colour the cell if not default
            if cell_bg not in (CELL_NONE, CELL_WIN if False else CELL_NONE):
                if cell_bg != row_bg:
                    draw.rectangle([x + 2, y + 2,
                                    x + col_widths[ci] - 2,
                                    y + ROW_H - 2],
                                   fill=cell_bg)
            fg = _text_colour(cell_bg) if cell_bg != row_bg else TEXT_BLK
            draw.text((x + 8, y + 8), str(cell_val), font=font_body, fill=fg)
            x += col_widths[ci]

        # Row border
        draw.line([PADDING, y + ROW_H,
                   total_w - PADDING, y + ROW_H],
                  fill=(210, 215, 225), width=1)
        y += ROW_H

    # Footer
    now = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")
    draw.text((PADDING, y + 6),
              f"SportsPoll  ·  {now}",
              font=_get_font(11), fill=(160, 160, 170))

    # Outer border
    draw.rectangle([PADDING - 1, TITLE_H + SUBTITLE_H + PADDING - 1,
                    total_w - PADDING + 1,
                    TITLE_H + SUBTITLE_H + PADDING + HDR_ROW_H +
                    len(rows) * ROW_H + 1],
                   outline=(180, 190, 210), width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


# ── Poll results ──────────────────────────────────────────────────────────────

def _build_poll_png(match: dict, votes: list[dict],
                    win_amounts: dict, display_names: dict,
                    tournament_name: str) -> bytes:
    options   = [o.strip() for o in match["options"].split("|") if o.strip()]
    total     = len(votes)
    by_opt    = {opt: [] for opt in options}
    voted_ids = set()

    for v in votes:
        opt = v.get("vote", "")
        if opt in by_opt:
            by_opt[opt].append(display_names.get(v["user_id"], v["user_id"]))
        voted_ids.add(v["user_id"])

    no_vote = sorted(
        display_names[u] for u in display_names if u not in voted_ids
    )

    headers = ["Option", "Votes", "%", "Win Points", "Voters"]
    rows    = []
    bgs     = []

    for opt in options:
        voters = by_opt[opt]
        count  = len(voters)
        pct    = f"{round(count / total * 100)}%" if total else "0%"
        amt    = win_amounts.get(opt, "—")
        names  = ", ".join(voters) if voters else "—"

        # Cell backgrounds per column
        amt_bg = CELL_WIN if amt.startswith("+") else CELL_LOSS
        rows.append([opt, str(count), pct, amt, names])
        bgs.append([CELL_NONE, CELL_NONE, CELL_NONE, amt_bg, CELL_NONE])

    if no_vote:
        rows.append(["Did not vote", "—", "—", "—", ", ".join(no_vote)])
        bgs.append([CELL_MISS, CELL_NONE, CELL_NONE, CELL_NONE, CELL_NONE])

    title    = f"Voting Results — {match['title']}"
    subtitle = (f"{tournament_name}  ·  "
                f"{match['match_date']} {match['start_time']} "
                f"{match['timezone'].split('/')[-1]}  ·  "
                f"{total} total votes")

    return _render_table_png(headers, rows, bgs, title, subtitle)


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

    # Plain HTML body
    rows_html = ""
    for opt in options:
        voters = by_opt[opt]
        count  = len(voters)
        pct    = round(count / total * 100) if total else 0
        amt    = win_amounts.get(opt, "—")
        names  = ", ".join(voters) if voters else "—"
        colour = "#16a34a" if amt.startswith("+") else "#dc2626"
        rows_html += f"""<tr>
          <td>{opt}</td><td>{count}</td><td>{pct}%</td>
          <td style="color:{colour};font-weight:700">{amt}</td>
          <td style="color:#555">{names}</td>
        </tr>"""

    no_vote_row = ""
    if no_vote:
        no_vote_row = (f'<tr><td colspan="5" style="color:#d97706">'
                       f'<b>Did not vote:</b> {", ".join(no_vote)}</td></tr>')

    html = f"""<!DOCTYPE html><html><body style="font-family:'Segoe UI',Arial,sans-serif;
background:#fff;padding:20px;color:#111">
<h2 style="color:#1a1f35">Voting Results — {match['title']}</h2>
<p><b>Tournament:</b> {tournament_name}<br>
<b>Date:</b> {match['match_date']} {match['start_time']} {match['timezone'].split('/')[-1]}<br>
<b>Total votes:</b> {total}</p>
<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;width:100%;font-size:14px">
<tr style="background:#1a1f35;color:#fff">
<th>Option</th><th>Votes</th><th>%</th><th>Win Points</th><th>Voters</th>
</tr>{rows_html}{no_vote_row}</table>
<p style="font-size:11px;color:#aaa;margin-top:16px">
See attached PNG for shareable version.</p>
</body></html>"""

    png = _build_poll_png(match, votes, win_amounts, display_names, tournament_name)
    _send(
        subject  = f"[{tournament_name}] {match['title']} — Voting Results",
        html_body= html,
        png_bytes= png,
        filename = f"poll_{match['match_id']}.png",
    )


# ── Leaderboard ───────────────────────────────────────────────────────────────

def _build_lb_png(match: dict, result: str,
                  leaderboard_rows: list[dict],
                  last5_match_ids: list[str],
                  last5_titles: dict,
                  tournament_name: str) -> bytes:

    m_hdrs   = [last5_titles.get(mid, mid[-6:]) for mid in last5_match_ids]
    headers  = ["#", "Player", "Points", "Win%", "Missed"] + m_hdrs
    rows     = []
    bgs      = []
    medals   = ["1", "2", "3"]

    for i, row in enumerate(leaderboard_rows):
        rank = medals[i] if i < 3 else str(i + 1)
        name = str(row.get("name", ""))
        pts  = float(row.get("total_points", 0))
        winp = float(row.get("win_pct", 0))
        miss = int(row.get("missed", 0))

        pts_str = f"+{pts:.2f}" if pts >= 0 else f"{pts:.2f}"
        pts_bg  = CELL_WIN if pts >= 0 else CELL_LOSS

        match_vals = []
        match_bgs  = []
        for mid in last5_match_ids:
            val = row.get(mid)
            bg  = _cell_bg(val)
            match_vals.append(_fmt_val(val))
            match_bgs.append(bg)

        miss_bg = CELL_MISS if miss > 0 else CELL_NONE
        rows.append([rank, name, pts_str, f"{winp:.0f}%",
                     str(miss)] + match_vals)
        bgs.append([CELL_NONE, CELL_NONE, pts_bg, CELL_NONE,
                    miss_bg] + match_bgs)

    title    = f"Leaderboard — {tournament_name}"
    subtitle = f"After {match['title']}  ·  Result: {result} Won"
    return _render_table_png(headers, rows, bgs, title, subtitle)


def send_leaderboard(match: dict, result: str,
                     leaderboard_rows: list[dict],
                     last5_match_ids: list[str],
                     last5_titles: dict,
                     tournament_name: str):

    m_hdrs    = "".join(f"<th>{last5_titles.get(mid,mid[-6:])}</th>"
                        for mid in last5_match_ids)
    medals    = ["🥇","🥈","🥉"]
    rows_html = ""

    for i, row in enumerate(leaderboard_rows):
        rank  = medals[i] if i < 3 else str(i + 1)
        name  = row.get("name","")
        pts   = float(row.get("total_points",0))
        winp  = float(row.get("win_pct",0))
        miss  = int(row.get("missed",0))
        pts_c = "#16a34a" if pts >= 0 else "#dc2626"
        pts_s = f"+{pts:.2f}" if pts >= 0 else f"{pts:.2f}"

        mcells = ""
        for mid in last5_match_ids:
            val = row.get(mid)
            if val is None:   mcells += "<td>—</td>"
            elif val == "miss": mcells += '<td style="color:#d97706">miss</td>'
            else:
                try:
                    f   = float(val)
                    c   = "#16a34a" if f > 0 else ("#dc2626" if f < 0 else "#555")
                    txt = f"+{f:.2f}" if f > 0 else (f"{f:.2f}" if f < 0 else "0")
                    mcells += f'<td style="color:{c}">{txt}</td>'
                except Exception:
                    mcells += f"<td>{val}</td>"

        rows_html += f"""<tr>
          <td style="text-align:center">{rank}</td>
          <td><b>{name}</b></td>
          <td style="color:{pts_c};font-weight:700">{pts_s}</td>
          <td>{winp:.0f}%</td><td>{miss}</td>{mcells}</tr>"""

    html = f"""<!DOCTYPE html><html><body style="font-family:'Segoe UI',Arial,sans-serif;
background:#fff;padding:20px;color:#111">
<h2 style="color:#1a1f35">Leaderboard — {tournament_name}</h2>
<p><b>After:</b> {match['title']}<br><b>Result:</b> {result} Won</p>
<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse;width:100%;font-size:14px">
<tr style="background:#1a1f35;color:#fff">
<th>#</th><th>Player</th><th>Points</th><th>Win%</th><th>Missed</th>{m_hdrs}
</tr>{rows_html}</table>
<p style="font-size:12px;color:#aaa;margin-top:12px">
Last {len(last5_match_ids)} completed matches (latest first).
See attached PNG for shareable version.</p>
</body></html>"""

    png = _build_lb_png(match, result, leaderboard_rows,
                        last5_match_ids, last5_titles, tournament_name)
    _send(
        subject  = f"[{tournament_name}] Leaderboard after {match['title']}",
        html_body= html,
        png_bytes= png,
        filename = f"leaderboard_{match['match_id']}.png",
    )


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
