"""
pages/home.py
Home page — tournament selector, three scrollable match frames.
  1. Upcoming    — voting open
  2. In Progress — voting closed, result not yet entered
  3. Past        — completed matches, newest first

Leaderboard button fix: uses st.rerun() immediately after setting state,
and syncs _last_nav to prevent navbar from overriding the navigation.
"""

import streamlit as st
from data.db import get_tournaments, get_matches, get_user_vote, get_points
from utils.timezone import is_voting_open, format_match_times, format_countdown

FRAME_HEIGHT = 460   # px — shows ~2.5 cards; scrolls for more


def show_home(user: dict):
    user_tz = user.get("timezone", "Asia/Kolkata") or "Asia/Kolkata"

    tournaments = get_tournaments()
    if not tournaments:
        st.info("No tournaments available yet.")
        return

    t_names = [t["name"] for t in tournaments]
    t_ids   = [t["tournament_id"] for t in tournaments]

    if "home_tournament_id" not in st.session_state:
        st.session_state["home_tournament_id"] = t_ids[0]

    cur_tid = st.session_state.get("home_tournament_id", t_ids[0])
    cur_idx = t_ids.index(cur_tid) if cur_tid in t_ids else 0

    sel_name = st.selectbox(
        "🏆 Select Tournament", t_names, index=cur_idx,
        label_visibility="collapsed", key="home_t_select"
    )
    sel_tid = t_ids[t_names.index(sel_name)]

    if sel_tid != st.session_state.get("home_tournament_id"):
        st.session_state["home_tournament_id"] = sel_tid

    all_matches = get_matches(tournament_id=sel_tid)
    if not all_matches:
        st.info("No matches scheduled yet.")
        return

    # Categorise
    upcoming    = [m for m in all_matches
                   if m["status"] == "upcoming" and is_voting_open(m)]
    in_progress = [m for m in all_matches
                   if m["status"] == "upcoming" and not is_voting_open(m)]
    completed   = [m for m in all_matches if m["status"] == "completed"]

    # ── 1. Upcoming — voting open ─────────────────────────────────────────────
    n_up = len(upcoming)
    st.markdown(f"### 📌 Upcoming Matches  ({n_up})")
    if not upcoming:
        st.caption("No upcoming matches with open voting.")
    else:
        with st.container(border=True, height=FRAME_HEIGHT):
            for idx, m in enumerate(upcoming):
                _card_upcoming(m, user["user_id"], user_tz, sel_tid, all_matches)
                if idx < n_up - 1:
                    st.divider()

    st.markdown("")

    # ── 2. In Progress — voting closed, awaiting result ───────────────────────
    n_ip = len(in_progress)
    st.markdown(f"### ⏳ In Progress  ({n_ip})")
    st.caption("Voting closed — result not yet entered by admin.")
    if not in_progress:
        st.caption("No matches in this state.")
    else:
        with st.container(border=True, height=min(FRAME_HEIGHT,
                                                   120 + n_ip * 80)):
            for idx, m in enumerate(in_progress):
                _card_in_progress(m, user["user_id"], user_tz, sel_tid, all_matches)
                if idx < n_ip - 1:
                    st.divider()

    st.markdown("")

    # ── 3. Past — completed matches, newest first ─────────────────────────────
    n_done = len(completed)
    st.markdown(f"### 📋 Past Matches  ({n_done})")
    if not completed:
        st.caption("No completed matches yet.")
    else:
        completed_desc = list(reversed(completed))
        with st.container(border=True, height=FRAME_HEIGHT):
            for idx, m in enumerate(completed_desc):
                _card_completed(m, user["user_id"], user_tz, sel_tid, all_matches)
                if idx < n_done - 1:
                    st.divider()

    st.markdown("---")

    # ── Leaderboard button ────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🏅 View Full Leaderboard", use_container_width=True,
                     key="home_lb_btn"):
            st.session_state["tournament_id"] = sel_tid
            st.session_state["page"]          = "leaderboard"
            # Sync _last_nav so navbar doesn't override this navigation
            st.session_state["_last_nav"]     = "leaderboard"
            st.rerun()


# ── Navigation helper ─────────────────────────────────────────────────────────

def _go_match(match_id: str, tournament_id: str, all_matches: list):
    st.session_state["page"]                = "match"
    st.session_state["match_id"]            = match_id
    st.session_state["match_tournament_id"] = tournament_id
    st.session_state["match_list"]          = [m["match_id"] for m in all_matches]
    # Sync _last_nav so navbar doesn't override
    st.session_state["_last_nav"]           = "match"
    st.rerun()


# ── Match cards ───────────────────────────────────────────────────────────────

def _card_upcoming(m, user_id, user_tz, tournament_id, all_matches):
    existing  = get_user_vote(user_id, m["match_id"])
    times     = format_match_times(m, user_tz)
    msg, sev  = format_countdown(m)

    c1, c2, c3 = st.columns([4, 3, 2])
    with c1:
        st.markdown(f"**{m['title']}**")
        st.caption(f"📍 {m['location']}   📅 {times['local']}")
        if times["user"]:
            st.caption(f"🕐 Your time: {times['user']}")
    with c2:
        if sev == "error":     st.error(msg, icon="🔴")
        elif sev == "warning": st.warning(msg, icon="⚠️")
        else:                  st.success(msg, icon="🟢")
    with c3:
        if existing:
            st.markdown(f"Your vote: **{existing['vote']}** ✅")
            label = "Change →"
        else:
            label = "Vote Now →"
        if st.button(label, key=f"home_btn_{m['match_id']}",
                     use_container_width=True, type="primary"):
            _go_match(m["match_id"], tournament_id, all_matches)


def _card_in_progress(m, user_id, user_tz, tournament_id, all_matches):
    existing = get_user_vote(user_id, m["match_id"])
    times    = format_match_times(m, user_tz)

    c1, c2, c3 = st.columns([4, 3, 2])
    with c1:
        st.markdown(f"**{m['title']}**")
        st.caption(f"📍 {m['location']}   📅 {times['local']}")
    with c2:
        st.warning("🔴 Voting closed — awaiting result", icon="⏳")
    with c3:
        if existing:
            st.markdown(f"You voted: **{existing['vote']}** ✅")
        else:
            st.caption("⚠️ No vote cast")
        if st.button("View →", key=f"ip_btn_{m['match_id']}",
                     use_container_width=True):
            _go_match(m["match_id"], tournament_id, all_matches)


def _card_completed(m, user_id, user_tz, tournament_id, all_matches):
    existing = get_user_vote(user_id, m["match_id"])
    result   = m.get("result", "")
    times    = format_match_times(m, user_tz)

    pts_list = get_points(user_id=user_id)
    pts      = next((float(p.get("total_points", 0)) for p in pts_list
                     if p["match_id"] == m["match_id"]), 0.0)

    c1, c2, c3 = st.columns([4, 3, 2])
    with c1:
        st.markdown(f"**{m['title']}**")
        st.caption(f"📍 {m['location']}   📅 {times['local']}")
    with c2:
        st.markdown(f"Result: **{result}**")
        if existing:
            correct = existing["vote"] == result
            st.caption(f"Your vote: {existing['vote']} {'✅' if correct else '❌'}")
        else:
            st.caption("⚠️ No vote cast")
    with c3:
        pts_str = f"+{pts:.2f}" if pts > 0 else f"{pts:.2f}"
        st.metric("Points", pts_str)
        if st.button("Details →", key=f"hist_{m['match_id']}",
                     use_container_width=True):
            _go_match(m["match_id"], tournament_id, all_matches)
