"""
pages/match.py
Match detail — voting, poll, result breakdown.

Rules:
  - Poll count/names hidden from regular users while voting open
  - Admin sees full voter list + can delete any vote while poll open
  - Result section only shown after poll closes AND result entered
"""

import streamlit as st
from data.db import (
    get_match, get_user_vote, cast_vote, update_vote,
    get_votes, delete_vote, get_points, get_all_users,
    is_registered, get_display_name
)
from utils.timezone import (
    is_voting_open, format_match_times, format_countdown, format_ts
)


def show_match(user: dict, match_id: str):
    match    = get_match(match_id)
    if not match:
        st.error(f"Match not found: {match_id}")
        return

    user_tz  = user.get("timezone", "Asia/Kolkata") or "Asia/Kolkata"
    is_admin = user.get("role") == "admin"
    options  = [o.strip() for o in match["options"].split("|") if o.strip()]
    times    = format_match_times(match, user_tz)
    msg, sev = format_countdown(match)
    voting   = is_voting_open(match)

    # ── Back ─────────────────────────────────────────────────────────────────
    if st.button("← Back"):
        st.session_state["page"] = "home"
        st.rerun()

    # ── Header ───────────────────────────────────────────────────────────────
    st.title(match["title"])
    st.caption(f"{match['tournament_id']}  ·  {match_id}")

    c1, c2, c3 = st.columns(3)
    c1.metric("📍 Location", match["location"])
    c2.metric("📅 Date",     match["match_date"])
    c3.metric("🕐 Local",    match["start_time"] + "  " +
              match["timezone"].split("/")[-1])

    if times["user"]:
        st.caption(f"Your time: **{times['user']}**   ·   UTC: {times['utc']}")
    else:
        st.caption(f"UTC: {times['utc']}")

    # ── Status banner ─────────────────────────────────────────────────────────
    if sev == "error":   st.error(msg)
    elif sev == "warning": st.warning(msg)
    else:                st.success(msg)

    st.markdown("---")

    # ── Voting ────────────────────────────────────────────────────────────────
    if voting:
        if not is_registered(user["user_id"], match["tournament_id"]):
            st.warning("Register for this tournament to vote.")
        else:
            _voting_section(match, options, user, user_tz)
    elif match["status"] == "upcoming":
        st.info("⏸️ Voting closed — result pending from admin.")

    # ── Poll summary ──────────────────────────────────────────────────────────
    st.markdown("---")
    _poll_summary(match, options, voting, is_admin)

    # ── Result (only after poll closes AND result entered) ────────────────────
    if match["status"] == "completed" and not voting:
        st.markdown("---")
        _result_section(match, options, user["user_id"])


# ── Voting UI ─────────────────────────────────────────────────────────────────

def _voting_section(match, options, user, user_tz):
    existing = get_user_vote(user["user_id"], match["match_id"])

    if existing:
        voted_at   = format_ts(existing.get("voted_at",   ""), user_tz)
        updated_at = format_ts(existing.get("updated_at", ""), user_tz)
        changes    = existing.get("update_count", 0)
        st.info(
            f"**Current vote: {existing['vote']}**   "
            f"| Cast: {voted_at}   "
            f"| Updated: {updated_at or '—'}   "
            f"| Changes: {changes}"
        )

    st.subheader("Cast / Update Your Vote")

    if len(options) <= 6:
        cols = st.columns(len(options))
        for i, opt in enumerate(options):
            selected = existing and existing["vote"] == opt
            label    = f"✅ {opt}" if selected else opt
            if cols[i].button(label, key=f"v_{opt}",
                              use_container_width=True,
                              type="primary" if selected else "secondary"):
                _submit_vote(user["user_id"], match, opt, existing)
    else:
        default = (options.index(existing["vote"])
                   if existing and existing["vote"] in options else 0)
        choice  = st.selectbox("Select your pick", options, index=default)
        if st.button("Confirm Vote", type="primary"):
            _submit_vote(user["user_id"], match, choice, existing)


def _submit_vote(user_id, match, option, existing):
    if not is_voting_open(match):
        st.error("Voting has closed.")
        return
    if existing:
        if existing["vote"] == option:
            st.warning(f"Already voted for {option}.")
            return
        update_vote(user_id, match["match_id"], option)
        st.success(f"Vote updated to **{option}** ✅")
    else:
        cast_vote(user_id, match["match_id"], match["tournament_id"], option)
        st.success(f"Vote cast for **{option}** ✅")
    st.rerun()


# ── Poll summary ──────────────────────────────────────────────────────────────

def _poll_summary(match, options, voting_open, is_admin):
    votes = get_votes(match_id=match["match_id"])
    total = len(votes)

    st.subheader("📊 Poll")

    if voting_open and not is_admin:
        # Regular users — hide all vote details while poll is open
        st.caption(
            f"**{total}** vote(s) cast so far — "
            "individual votes and counts shown after voting closes."
        )
        return

    if total == 0:
        st.caption("No votes cast yet.")
        return

    # Breakdown visible to admin (always) and everyone after poll closes
    all_users = get_all_users()
    umap      = {u["user_id"]: get_display_name(u["user_id"]) for u in all_users}

    st.caption(f"{total} total votes")

    for opt in options:
        opt_votes = [v for v in votes if v["vote"] == opt]
        count     = len(opt_votes)
        pct       = round(count / total * 100) if total else 0
        bar       = "█" * (pct // 5) + "░" * (20 - pct // 5)
        st.markdown(f"`{opt:<22} {bar}  {pct}%  ({count} votes)`")

        # Admin-only voter list with delete button (while poll open OR closed)
        if is_admin and opt_votes:
            with st.expander(f"Voters for {opt} — admin view"):
                for v in opt_votes:
                    dname = umap.get(v["user_id"], v["user_id"])
                    c1, c2, c3 = st.columns([3, 3, 1])
                    c1.markdown(f"👤 **{dname}**")
                    c2.caption(f"voted {v.get('voted_at', '')[:16]}")
                    if c3.button("🗑️", key=f"dv_{v['vote_id']}",
                                  help=f"Delete {dname}'s vote"):
                        delete_vote(v["user_id"], match["match_id"])
                        st.success(f"Vote by **{dname}** deleted.")
                        st.rerun()


# ── Result breakdown ──────────────────────────────────────────────────────────

def _result_section(match, options, user_id):
    result   = match.get("result", "")
    votes    = get_votes(match_id=match["match_id"])
    pts_list = get_points()
    users    = get_all_users()
    umap     = {u["user_id"]: get_display_name(u["user_id"]) for u in users}

    st.subheader(f"🏆 Result: {result} Won")

    winner_pts = 0.0
    for p in pts_list:
        if (p["match_id"] == match["match_id"]
                and float(p.get("total_points", 0)) > 0):
            winner_pts = float(p["total_points"])
            break
    if winner_pts:
        st.caption(f"Points awarded to correct voters: **+{winner_pts}** each")

    for opt in options:
        opt_votes = [v for v in votes if v["vote"] == opt]
        is_win    = opt == result
        icon      = "✅" if is_win else "❌"
        pts_label = (f"  —  +{winner_pts} pts each"
                     if is_win and winner_pts else "  —  0 pts")

        with st.expander(f"{icon}  **{opt}** voters{pts_label}  ({len(opt_votes)})"):
            if not opt_votes:
                st.caption("No votes.")
            else:
                for v in opt_votes:
                    name  = umap.get(v["user_id"], v["user_id"])
                    u_pts = next(
                        (float(p["total_points"]) for p in pts_list
                         if p["user_id"] == v["user_id"]
                         and p["match_id"] == match["match_id"]), 0.0
                    )
                    st.markdown(
                        f"👤 **{name}**   "
                        f"voted {v.get('voted_at', '')[:16]}   "
                        f"{'  +' + str(u_pts) + ' pts' if u_pts > 0 else '  0 pts'}"
                    )

    missed_pts = [
        p for p in pts_list
        if p["match_id"] == match["match_id"]
        and ("miss" in p.get("note", "") or "penalty" in p.get("note", ""))
    ]
    if missed_pts:
        with st.expander(f"⚠️  Missed / Penalised  ({len(missed_pts)})"):
            for p in missed_pts:
                name = umap.get(p["user_id"], p["user_id"])
                st.markdown(
                    f"👤 **{name}**   {p['note']}   "
                    f"{float(p['total_points'])} pts"
                )
