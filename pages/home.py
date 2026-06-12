"""
pages/home.py
Home page — tournament selector, upcoming and past matches.
No registration required — users can vote in any tournament directly.
Tournament selection persisted in session so Back from match returns here.
"""

import streamlit as st
from data.db import (
    get_tournaments, get_matches, get_user_vote, get_points
)
from utils.timezone import is_voting_open, format_match_times, format_countdown


def show_home(user: dict):
    user_tz = user.get("timezone", "Asia/Kolkata") or "Asia/Kolkata"

    tournaments = get_tournaments()
    if not tournaments:
        st.info("No tournaments available yet. Ask the admin to create one.")
        return

    t_names = [t["name"] for t in tournaments]
    t_ids   = [t["tournament_id"] for t in tournaments]

    # Persist tournament selection in session — Back from match returns here
    if "home_tournament_id" not in st.session_state:
        st.session_state["home_tournament_id"] = t_ids[0]

    cur_tid = st.session_state.get("home_tournament_id", t_ids[0])
    cur_idx = t_ids.index(cur_tid) if cur_tid in t_ids else 0

    sel_name = st.selectbox(
        "🏆 Select Tournament", t_names,
        index=cur_idx,
        label_visibility="collapsed",
        key="home_t_select"
    )
    sel_tid = t_ids[t_names.index(sel_name)]

    # Update session if user explicitly changed tournament
    if sel_tid != st.session_state.get("home_tournament_id"):
        st.session_state["home_tournament_id"] = sel_tid

    all_matches = get_matches(tournament_id=sel_tid)
    if not all_matches:
        st.info("No matches scheduled yet.")
        return

    upcoming  = [m for m in all_matches if m["status"] == "upcoming"]
    completed = [m for m in all_matches if m["status"] == "completed"]

    st.markdown("### 📌 Upcoming Matches")
    if not upcoming:
        st.caption("No upcoming matches.")
    else:
        for m in upcoming:
            _card_upcoming(m, user["user_id"], user_tz, sel_tid, all_matches)

    st.markdown("---")

    st.markdown("### 📋 Past Matches")
    if not completed:
        st.caption("No completed matches yet.")
    else:
        for m in completed:
            _card_completed(m, user["user_id"], user_tz, sel_tid, all_matches)

    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🏅 View Full Leaderboard", use_container_width=True):
            st.session_state["tournament_id"] = sel_tid
            st.session_state["page"]          = "leaderboard"
            st.session_state["_last_nav"]     = "leaderboard"
            st.rerun()


def _go_match(match_id: str, tournament_id: str, all_matches: list):
    """Navigate to match page, storing context for Next/Prev/Back."""
    st.session_state["page"]                = "match"
    st.session_state["match_id"]            = match_id
    st.session_state["match_tournament_id"] = tournament_id
    st.session_state["match_list"]          = [m["match_id"] for m in all_matches]
    st.session_state["_last_nav"]           = "home"
    st.rerun()


def _card_upcoming(m: dict, user_id: str, user_tz: str,
                   tournament_id: str, all_matches: list):
    existing  = get_user_vote(user_id, m["match_id"])
    times     = format_match_times(m, user_tz)
    msg, sev  = format_countdown(m)
    open_vote = is_voting_open(m)

    with st.container(border=True):
        c1, c2, c3 = st.columns([4, 3, 2])
        with c1:
            st.markdown(f"**{m['title']}**")
            st.caption(f"📍 {m['location']}   📅 {times['local']}")
            if times["user"]:
                st.caption(f"🕐 Your time: {times['user']}")
        with c2:
            if sev == "error":   st.error(msg, icon="🔴")
            elif sev == "warning": st.warning(msg, icon="⚠️")
            else:                st.success(msg, icon="🟢")
        with c3:
            if existing:
                st.markdown(f"Your vote: **{existing['vote']}** ✅")
                label = "Change Vote →"
            else:
                label = "Vote Now →"
            if open_vote:
                if st.button(label, key=f"home_btn_{m['match_id']}",
                             use_container_width=True, type="primary"):
                    _go_match(m["match_id"], tournament_id, all_matches)
            else:
                st.caption("Voting closed")


def _card_completed(m: dict, user_id: str, user_tz: str,
                    tournament_id: str, all_matches: list):
    existing = get_user_vote(user_id, m["match_id"])
    result   = m.get("result", "")
    times    = format_match_times(m, user_tz)

    pts_list = get_points(user_id=user_id)
    pts      = next((float(p.get("total_points", 0)) for p in pts_list
                     if p["match_id"] == m["match_id"]), 0.0)

    with st.container(border=True):
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
            pts_str = f"+{pts}" if pts > 0 else str(pts)
            st.metric("Points", pts_str)
            if st.button("Details →", key=f"hist_{m['match_id']}",
                         use_container_width=True):
                _go_match(m["match_id"], tournament_id, all_matches)
