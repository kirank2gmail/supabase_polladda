"""
utils/email_sender.py
Sends formatted HTML emails via Gmail SMTP.
Images generated using Pillow for easy sharing.

Two email types:
  1. send_poll_results()   — after poll closes, shows votes + calculated win amounts
  2. send_leaderboard()    — after result entered, shows leaderboard + last 5 match points
"""

import smtplib
import io
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from email.mime.base      import MIMEBase
from email               import encoders
from datetime            import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

import streamlit as st


# ── Config ────────────────────────────────────────────────────────────────────

def _email_cfg():
    cfg = st.secrets.get("email", {})
    return cfg.get("sender", ""), cfg.get("app_password", ""), cfg.get("recipient", "")

def email_configured() -> bool:
    s, p, r = _email_cfg()
    return bool(s and p and r)


# ── Colour palette ────────────────────────────────────────────────────────────

BG        = (15,  17,  23)    # dark background
PANEL     = (30,  33,  45)    # card background
BORDER    = (50,  55,  70)    # border colour
WHITE     = (255, 255, 255)
GOLD      = (255, 200,  50)
GREEN     = ( 80, 200, 120)
RED       = (220,  80,  80)
GREY      = (160, 165, 180)
ACCENT    = (100, 140, 255)


def _font(size: int = 16):
    """Return a PIL font — falls back to default if no TTF available."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", size)
        except Exception:
            return ImageFont.load_default()

def _font_bold(size: int = 16):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return _font(size)


# ── Poll results image ────────────────────────────────────────────────────────

def build_poll_image(match: dict, votes: list[dict],
                     win_amounts: dict,        # option → points string e.g. "+1.50"
                     display_names: dict,      # user_id → nickname
                     tournament_name: str) -> bytes:
    """
    Renders a poll results card as PNG bytes.

    Layout:
      Header: Tournament | Match title | Date
      Per-option row: option name | bar | vote% | voters list | win pts
      Footer: total votes
    """
    options     = [o.strip() for o in match["options"].split("|") if o.strip()]
    total_votes = len(votes)

    # Group voters per option
    voters_by_opt = {opt: [] for opt in options}
    for v in votes:
        opt = v.get("vote","")
        if opt in voters_by_opt:
            voters_by_opt[opt].append(display_names.get(v["user_id"], v["user_id"]))

    # Voted user IDs
    voted_ids   = {v["user_id"] for v in votes}

    # Canvas sizing
    W           = 900
    ROW_H       = 90
    HEADER_H    = 100
    FOOTER_H    = 60
    H           = HEADER_H + len(options) * ROW_H + FOOTER_H + 20

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill=PANEL)
    draw.rectangle([0, HEADER_H-2, W, HEADER_H], fill=ACCENT)

    draw.text((24, 16), tournament_name, font=_font_bold(15), fill=GREY)
    draw.text((24, 38), match["title"],  font=_font_bold(26), fill=WHITE)
    draw.text((24, 72), f"📍 {match['location']}   📅 {match['match_date']}  {match['start_time']}",
              font=_font(14), fill=GREY)

    draw.text((W-200, 38), "VOTING RESULTS", font=_font_bold(14), fill=ACCENT)
    draw.text((W-200, 60), f"{total_votes} total votes",
              font=_font(13), fill=GREY)

    # ── Option rows ───────────────────────────────────────────────────────────
    BAR_X   = 220
    BAR_W   = 300
    WIN_X   = W - 180

    for i, opt in enumerate(options):
        y       = HEADER_H + i * ROW_H
        count   = len(voters_by_opt[opt])
        pct     = round(count / total_votes * 100) if total_votes else 0
        win_amt = win_amounts.get(opt, "—")
        voters  = voters_by_opt[opt]

        # Row background (alternating)
        row_bg  = (22, 25, 35) if i % 2 == 0 else (26, 29, 42)
        draw.rectangle([0, y, W, y + ROW_H - 1], fill=row_bg)
        draw.line([0, y + ROW_H - 1, W, y + ROW_H - 1], fill=BORDER, width=1)

        # Option name
        draw.text((24, y + 18), opt, font=_font_bold(18), fill=WHITE)
        draw.text((24, y + 44), f"{count} vote{'s' if count != 1 else ''}",
                  font=_font(13), fill=GREY)

        # Progress bar
        bar_filled = int(BAR_W * pct / 100)
        draw.rectangle([BAR_X, y + 28, BAR_X + BAR_W, y + 52],
                       fill=BORDER, outline=BORDER)
        if bar_filled > 0:
            draw.rectangle([BAR_X, y + 28, BAR_X + bar_filled, y + 52],
                           fill=ACCENT)
        draw.text((BAR_X + BAR_W + 10, y + 30), f"{pct}%",
                  font=_font_bold(16), fill=WHITE)

        # Voters list (truncated)
        voters_str = ", ".join(voters[:6])
        if len(voters) > 6:
            voters_str += f" +{len(voters)-6} more"
        draw.text((BAR_X, y + 60), voters_str or "—",
                  font=_font(12), fill=GREY)

        # Win amount
        amt_colour = GREEN if win_amt.startswith("+") else RED
        draw.text((WIN_X, y + 20), "If correct:",
                  font=_font(12), fill=GREY)
        draw.text((WIN_X, y + 38), win_amt,
                  font=_font_bold(22), fill=amt_colour)

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = HEADER_H + len(options) * ROW_H + 10
    draw.line([24, fy, W-24, fy], fill=BORDER, width=1)
    draw.text((24, fy + 12),
              f"Poll closed  ·  Generated {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
              font=_font(12), fill=GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


# ── Leaderboard image ─────────────────────────────────────────────────────────

def build_leaderboard_image(match: dict, result: str,
                             leaderboard_rows: list[dict],
                             last5_match_ids: list[str],
                             last5_titles: dict,    # match_id → short title
                             tournament_name: str) -> bytes:
    """
    Renders a leaderboard card as PNG bytes.

    Columns: Rank | Player | Total Pts | Win% | last 5 match pts...
    """
    COL_RANK  = 50
    COL_NAME  = 160
    COL_PTS   = 120
    COL_WIN   = 90
    COL_MATCH = 90
    COLS      = [COL_RANK, COL_NAME, COL_PTS, COL_WIN] + [COL_MATCH] * len(last5_match_ids)

    W         = sum(COLS) + 48
    ROW_H     = 48
    HEADER_H  = 110
    COL_HDR_H = 40
    FOOTER_H  = 40
    H         = HEADER_H + COL_HDR_H + len(leaderboard_rows) * ROW_H + FOOTER_H

    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # ── Header ────────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, W, HEADER_H], fill=PANEL)
    draw.rectangle([0, HEADER_H-2, W, HEADER_H], fill=GOLD)

    draw.text((24, 14), tournament_name,  font=_font_bold(14), fill=GREY)
    draw.text((24, 36), "🏆 Leaderboard", font=_font_bold(28), fill=WHITE)
    draw.text((24, 74), f"After: {match['title']}  —  Result: {result} Won",
              font=_font(15), fill=GOLD)

    # ── Column headers ────────────────────────────────────────────────────────
    cy   = HEADER_H
    draw.rectangle([0, cy, W, cy + COL_HDR_H], fill=(20, 22, 34))

    x    = 24
    hdrs = ["#", "Player", "Total", "Win%"] + \
           [last5_titles.get(mid, mid[-4:]) for mid in last5_match_ids]

    for i, hdr in enumerate(hdrs):
        draw.text((x + 4, cy + 10), hdr, font=_font_bold(13), fill=ACCENT)
        x += COLS[i]

    # ── Data rows ─────────────────────────────────────────────────────────────
    for ri, row in enumerate(leaderboard_rows):
        ry     = HEADER_H + COL_HDR_H + ri * ROW_H
        row_bg = (18, 20, 30) if ri % 2 == 0 else (22, 25, 38)
        draw.rectangle([0, ry, W, ry + ROW_H - 1], fill=row_bg)
        draw.line([0, ry + ROW_H - 1, W, ry + ROW_H - 1], fill=BORDER, width=1)

        x     = 24
        rank  = str(row.get("rank", ri+1))
        name  = str(row.get("name", ""))[:16]
        pts   = f"{float(row.get('total_points',0)):+.2f}"
        winp  = f"{float(row.get('win_pct',0)):.0f}%"

        # Rank medal for top 3
        rank_colour = [GOLD, GREY, (205,127,50)][ri] if ri < 3 else WHITE
        draw.text((x + 4, ry + 14), rank, font=_font_bold(16), fill=rank_colour)
        x += COLS[0]

        draw.text((x + 4, ry + 14), name, font=_font_bold(15), fill=WHITE)
        x += COLS[1]

        pts_col = GREEN if float(row.get("total_points",0)) >= 0 else RED
        draw.text((x + 4, ry + 14), pts, font=_font_bold(15), fill=pts_col)
        x += COLS[2]

        draw.text((x + 4, ry + 14), winp, font=_font(14), fill=GREY)
        x += COLS[3]

        # Last 5 match columns
        for mid in last5_match_ids:
            val = row.get(mid)
            if val is None:
                txt   = "—"
                color = GREY
            elif val == "miss":
                txt   = "⚠"
                color = (200, 150, 50)
            else:
                try:
                    f     = float(val)
                    txt   = f"{f:+.2f}" if f != 0 else "−1.00"
                    color = GREEN if f > 0 else RED
                except Exception:
                    txt   = str(val)
                    color = GREY
            draw.text((x + 4, ry + 14), txt, font=_font(13), fill=color)
            x += COL_MATCH

    # ── Footer ────────────────────────────────────────────────────────────────
    fy = HEADER_H + COL_HDR_H + len(leaderboard_rows) * ROW_H + 8
    draw.text((24, fy),
              f"Generated {datetime.utcnow().strftime('%d %b %Y %H:%M UTC')}",
              font=_font(12), fill=GREY)

    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(150, 150))
    return buf.getvalue()


# ── Send email ────────────────────────────────────────────────────────────────

def _send(subject: str, body_html: str, image_bytes: bytes,
          image_filename: str):
    sender, app_password, recipient = _email_cfg()
    if not all([sender, app_password, recipient]):
        raise ValueError("Email not configured in secrets.toml")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient

    # HTML body
    msg.attach(MIMEText(body_html, "html"))

    # Image attachment
    img_part = MIMEBase("image", "png")
    img_part.set_payload(image_bytes)
    encoders.encode_base64(img_part)
    img_part.add_header("Content-Disposition",
                        "attachment", filename=image_filename)
    msg.attach(img_part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.sendmail(sender, recipient, msg.as_string())


# ── Public API ────────────────────────────────────────────────────────────────

def send_poll_results(match: dict, votes: list[dict],
                      win_amounts: dict, display_names: dict,
                      tournament_name: str):
    """
    Send poll results email after poll closes.
    win_amounts: {option: "+1.50 pts"} — calculated before result
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow not installed. Add 'Pillow' to requirements.txt")

    img_bytes = build_poll_image(
        match, votes, win_amounts, display_names, tournament_name
    )

    options = [o.strip() for o in match["options"].split("|") if o.strip()]
    total   = len(votes)

    body = f"""
    <html><body style="font-family:sans-serif;background:#0e1117;color:#fff;padding:20px;">
    <h2>📊 Voting Results — {match['title']}</h2>
    <p><b>Tournament:</b> {tournament_name}<br>
       <b>Match:</b> {match['title']}<br>
       <b>Total votes:</b> {total}</p>
    <p>See attached image for full breakdown.</p>
    <hr>
    <p style="color:#888;font-size:12px;">SportsPoll automated email</p>
    </body></html>
    """

    filename = f"poll_results_{match['match_id']}.png"
    subject  = f"[{tournament_name}] {match['title']} — Voting Results"

    _send(subject, body, img_bytes, filename)


def send_leaderboard(match: dict, result: str,
                     leaderboard_rows: list[dict],
                     last5_match_ids: list[str],
                     last5_titles: dict,
                     tournament_name: str):
    """
    Send leaderboard email after result is entered and points calculated.
    """
    if not PIL_AVAILABLE:
        raise ImportError("Pillow not installed. Add 'Pillow' to requirements.txt")

    img_bytes = build_leaderboard_image(
        match, result, leaderboard_rows,
        last5_match_ids, last5_titles, tournament_name
    )

    body = f"""
    <html><body style="font-family:sans-serif;background:#0e1117;color:#fff;padding:20px;">
    <h2>🏆 Leaderboard Update — {tournament_name}</h2>
    <p><b>After:</b> {match['title']}<br>
       <b>Result:</b> {result} Won</p>
    <p>See attached image for full leaderboard with last 5 match points.</p>
    <hr>
    <p style="color:#888;font-size:12px;">SportsPoll automated email</p>
    </body></html>
    """

    filename = f"leaderboard_{match['match_id']}.png"
    subject  = f"[{tournament_name}] Leaderboard after {match['title']}"

    _send(subject, body, img_bytes, filename)
