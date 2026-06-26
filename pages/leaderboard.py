"""
pages/leaderboard.py
Leaderboard page — delegates all data assembly to leaderboard_builder.
Owns only HTML rendering and Streamlit UI logic.
"""

import streamlit as st
from data.db import get_tournaments
from data.leaderboard_builder import (
    build_lb_data, match_label, cell_text, cell_colours, cell_num
)


def _cell_html(val) -> str:
    """Return a styled <td> for a match-cell value."""
    txt      = cell_text(val)
    fg, bg   = cell_colours(val)
    is_blank = val is None or val == ""

    if is_blank:
        return f'<td style="color:{fg};text-align:right">—</td>'

    align = "center" if val in ("A", "Q", "miss", "M") else "right"
    bg_style = f"background:{bg};" if bg else ""
    return (f'<td style="{bg_style}color:{fg};text-align:{align};'
            f'font-weight:600">{txt}</td>')


def show_leaderboard(user: dict):
    tournaments = get_tournaments()
    if not tournaments:
        st.info("No tournaments yet.")
        return

    t_names = [t["name"] for t in tournaments]
    t_ids   = [t["tournament_id"] for t in tournaments]
    pre_tid = st.session_state.get("tournament_id", t_ids[0])
    pre_idx = t_ids.index(pre_tid) if pre_tid in t_ids else 0

    sel_name = st.selectbox("🏆 Tournament", t_names, index=pre_idx)
    sel_tid  = t_ids[t_names.index(sel_name)]

    data = build_lb_data(sel_tid)
    rows          = data["rows"]
    matches_asc   = data["matches_asc"]
    match_ids_desc= data["match_ids_desc"]
    col_match_ids = data["col_match_ids"]
    labels        = data["labels"]
    col_totals    = data["col_totals"]
    grand_total   = data["grand_total"]
    bank          = data["bank"]
    heroes        = data["heroes"]

    if not rows:
        st.info("No results recorded yet for this tournament.")
        return

    # ── Hero stats ────────────────────────────────────────────────────────────
    if heroes:
        st.markdown("### 🎖️ Highlights")
        h1, h2, h3 = st.columns(3)
        with h1:
            with st.container(border=True):
                st.markdown("🔥 **Longest Win Streak**")
                hw = heroes["top_win_streak"]
                st.markdown(f"**{hw['names']}**")
                st.caption(f"{hw['value']} consecutive wins (misses ignored)")
        with h2:
            with st.container(border=True):
                st.markdown("💀 **Longest Loss Streak**")
                hl = heroes["top_loss_streak"]
                st.markdown(f"**{hl['names']}**")
                st.caption(f"{hl['value']} consecutive losses (misses ignored)")
        with h3:
            with st.container(border=True):
                st.markdown("⚠️ **Most Missed Votes**")
                hm = heroes["top_missed"]
                st.markdown(f"**{hm['names']}**")
                st.caption(f"{hm['value']} missed")

    st.markdown("---")

    # ── CSV download (built before sort so always points-ordered) ─────────────
    import pandas as pd, io

    fixed_cols = ["rank", "name", "total_points", "win_pct", "missed"]
    df = pd.DataFrame(rows)
    df = df[[c for c in fixed_cols + match_ids_desc if c in df.columns]]
    df = df.rename(columns={
        "rank": "#", "name": "Player", "total_points": "Points",
        "win_pct": "Win%", "missed": "Missed",
    })
    rename_map = {mid: labels[mid] for mid in match_ids_desc if mid in labels}
    df = df.rename(columns=rename_map)
    for col in rename_map.values():
        if col in df.columns:
            df[col] = df[col].apply(cell_text)

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False)
    csv_bytes = csv_buf.getvalue().encode()

    # ── Sort control ──────────────────────────────────────────────────────────
    SORT_OPTIONS = {
        "Points"      : ("total_points", True),
        "Win %"       : ("win_pct",      True),
        "Alphabetical": ("name",         False),
    }
    sort_col, _ = st.columns([2, 6])
    sort_choice  = sort_col.selectbox(
        "Sort by", list(SORT_OPTIONS.keys()), index=0, key="lb_sort"
    )
    sort_key, sort_desc = SORT_OPTIONS[sort_choice]
    rows = sorted(rows,
                  key=lambda r: r.get(sort_key, 0 if sort_desc else ""),
                  reverse=sort_desc)
    for i, r in enumerate(rows):
        r["rank"] = i + 1

    st.markdown("### 📊 Leaderboard")

    # ── Build HTML table ──────────────────────────────────────────────────────
    m_labels  = [labels[mid] for mid in col_match_ids]
    th_base   = "padding:10px 12px;font-weight:700;font-size:14px;white-space:nowrap"
    th_l      = f"{th_base};text-align:left"
    th_r      = f"{th_base};text-align:right"
    th_c      = f"{th_base};text-align:center"

    header_html = (
        f'<th style="{th_c}">#</th>'
        f'<th style="{th_l}">Player</th>'
        f'<th style="{th_r}">Points</th>'
        f'<th style="{th_r}">Win%</th>'
        f'<th style="{th_r}">Missed</th>'
    )
    for lbl in m_labels:
        header_html += f'<th style="{th_c}">{lbl}</th>'

    medals    = ["🥇", "🥈", "🥉"]
    rows_html = ""

    for i, row in enumerate(rows):
        rank   = medals[i] if i < 3 else str(i + 1)
        name   = row.get("name", "")
        pts    = float(row.get("total_points", 0))
        winp   = float(row.get("win_pct", 0))
        missed = int(row.get("missed", 0))

        bg      = "#f9f9f9" if i % 2 == 1 else "#ffffff"
        pts_col = "#0e6e24" if pts >= 0 else "#a01414"
        pts_bg  = "#d1f0d7" if pts >= 0 else "#fcd7d7"
        pts_str = f"+{pts:.2f}" if pts >= 0 else f"{pts:.2f}"
        miss_bg = "#fff3cd" if missed > 0 else bg
        miss_fg = "#8c5500" if missed > 0 else "#111"
        td      = "padding:9px 12px;font-size:14px;border-bottom:1px solid #e8e8e8"

        row_html = (
            f'<td style="{td};text-align:center;background:{bg}">{rank}</td>'
            f'<td style="{td};background:{bg};font-weight:600">{name}</td>'
            f'<td style="{td};text-align:right;background:{pts_bg};color:{pts_col};font-weight:700">{pts_str}</td>'
            f'<td style="{td};text-align:right;background:{bg};color:#555">{winp:.0f}%</td>'
            f'<td style="{td};text-align:right;background:{miss_bg};color:{miss_fg};font-weight:600">{missed}</td>'
        )
        for mid in col_match_ids:
            row_html += _cell_html(row.get(mid))
        rows_html += f'<tr style="background:{bg}">{row_html}</tr>'

    st.caption(
        "Latest match first  ·  "
        "<span style='background:#d1f0d7;padding:1px 6px;border-radius:3px;font-size:12px;color:#0e6e24'>Win</span> &nbsp;"
        "<span style='background:#fcd7d7;padding:1px 6px;border-radius:3px;font-size:12px;color:#a01414'>Loss</span> &nbsp;"
        "<span style='background:#fff3cd;padding:1px 6px;border-radius:3px;font-size:12px;color:#8c5500'>M=miss</span> &nbsp;"
        "<span style='background:#e0e0e0;padding:1px 6px;border-radius:3px;font-size:12px;color:#777'>A=abandoned</span> &nbsp;"
        "<span style='background:#e8e0f0;padding:1px 6px;border-radius:3px;font-size:12px;color:#5a3e8a'>Q=quit</span>",
        unsafe_allow_html=True
    )

    # ── Total row ─────────────────────────────────────────────────────────────
    td_tot = "padding:9px 12px;font-size:14px;font-weight:700;border-top:2px solid #28324f;background:#f0f4ff;white-space:nowrap"
    gc     = "#0e6e24" if grand_total >= 0 else "#a01414"
    total_row_html = (
        f'<td style="{td_tot};text-align:center">—</td>'
        f'<td style="{td_tot}">Total</td>'
        f'<td style="{td_tot};text-align:right;color:{gc}">{"+" if grand_total>=0 else ""}{grand_total:.2f}</td>'
        f'<td style="{td_tot}"></td>'
        f'<td style="{td_tot}"></td>'
    )
    for mid in col_match_ids:
        t     = col_totals.get(mid, 0.0)
        color = "#0e6e24" if t > 0 else ("#a01414" if t < 0 else "#555")
        val   = f"+{t:.2f}" if t > 0 else (f"{t:.2f}" if t < 0 else "0")
        total_row_html += f'<td style="{td_tot};text-align:right;color:{color}">{val}</td>'

    table_html = f"""
    <style>
      .lb-table {{ width:100%; border-collapse:collapse; font-family:Arial,sans-serif; }}
      .lb-table td, .lb-table th {{ white-space:nowrap; }}
    </style>
    <div style="overflow-x:auto;border-radius:6px;border:1px solid #ddd;margin-top:8px">
      <table class="lb-table">
        <thead><tr style="background:#28324f;color:#ffffff">{header_html}</tr></thead>
        <tbody>{rows_html}<tr>{total_row_html}</tr></tbody>
      </table>
    </div>
    """
    st.html(table_html)

    # Bank
    bank_str   = f"+{bank:.2f}" if bank > 0 else f"{bank:.2f}"
    bank_color = "#0e6e24" if bank > 0 else ("#a01414" if bank < 0 else "#555")
    st.markdown(
        f"🏦 **Bank:** <span style='color:{bank_color};font-weight:700'>{bank_str}</span> pts",
        unsafe_allow_html=True
    )

    st.download_button(
        "⬇️ Download CSV", data=csv_bytes,
        file_name=f"leaderboard_{sel_tid}.csv",
        mime="text/csv", key="lb_download"
    )

    # ── Match Details — bordered frame, 6 per row ─────────────────────────────
    if match_ids_desc:
        st.markdown("")
        st.markdown("#### 🔍 Match Details")
        COLS_PER_ROW = 6
        chunks  = [match_ids_desc[i:i+COLS_PER_ROW]
                   for i in range(0, len(match_ids_desc), COLS_PER_ROW)]
        frame_h = min(len(chunks), 5) * 48 * 2 + 16

        with st.container(border=True, height=frame_h):
            for chunk in chunks:
                cols = st.columns(COLS_PER_ROW)
                for ci, mid in enumerate(chunk):
                    m   = next((x for x in matches_asc if x["match_id"] == mid), None)
                    tip = m["title"] if m else mid
                    with cols[ci]:
                        if st.button(labels[mid], key=f"lb_{mid}",
                                     help=tip, use_container_width=True):
                            st.session_state["page"]                = "match"
                            st.session_state["match_id"]            = mid
                            st.session_state["match_list"]          = [x["match_id"] for x in matches_asc]
                            st.session_state["match_tournament_id"] = sel_tid
                            st.session_state["_last_nav"]           = "leaderboard"
                            st.rerun()
                for ci in range(len(chunk), COLS_PER_ROW):
                    cols[ci].empty()
