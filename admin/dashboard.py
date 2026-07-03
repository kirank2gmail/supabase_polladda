"""
admin/dashboard.py — Admin panel.
Changes: delete_tournament option added to tournaments tab.
"""

import streamlit as st
import pandas as pd
from datetime import date, time
from data.db import (
    tournament_id_exists, match_id_exists_in_tournament,
    get_all_users, create_user, delete_user, set_user_role,
    get_display_name, change_password,
    get_tournaments, create_tournament, update_tournament_status, delete_tournament,
    get_matches, create_match, bulk_create_matches, delete_match,
    get_votes, delete_vote, get_user_by_id, verify_password,
    get_penalties, add_penalty, delete_penalty,
)
from data.points import recalculate_tournament, apply_match_result
from data.match_players import (
    quit_player, reinstate_player, get_player_quit_status,
    apply_miss_floor, remove_miss_floor, get_miss_floor_status,
    _match_ist_label,
)
from utils.email_sender import send_result_emails, email_configured
from utils.timezone import COMMON_TIMEZONES, get_match_cutoff_utc, is_voting_open, format_ts
from utils.match_helpers import (
    parse_time as _parse_time,
    options_from_title as _options_from_title,
    validate_options as _validate_options,
)


def show_admin(user: dict):
    st.title("⚙️ Admin Panel")
    st.caption(f"Logged in as **{get_display_name(user['user_id'])}**")
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "👥 Users", "🏆 Tournaments", "📋 Matches", "🎯 Results", "🚪 Player Quit"
    ])
    with tab1: _users_tab(user)
    with tab2: _tournaments_tab(user)
    with tab3: _matches_tab(user)
    with tab4: _results_tab()
    with tab5: _quit_tab()


# ── Users ─────────────────────────────────────────────────────────────────────

def _users_tab(admin: dict):
    st.subheader("Create New User")
    st.caption("Nickname defaults to first name. User must change password on first login.")
    with st.form("create_user"):
        c1, c2 = st.columns(2)
        uname  = c1.text_input("Username", placeholder="john")
        role   = c2.selectbox("Role", ["user", "admin"])
        pw     = c1.text_input("Temporary Password", type="password",
                                placeholder="min 6 characters")
        pw2    = c2.text_input("Confirm Password", type="password")
        if st.form_submit_button("Create User", type="primary"):
            if not uname.strip():
                st.error("Username required.")
            elif len(pw) < 6:
                st.error("Password must be at least 6 characters.")
            elif pw != pw2:
                st.error("Passwords do not match.")
            elif any(u["username"].lower() == uname.lower() for u in get_all_users()):
                st.error("Username already exists.")
            else:
                new_u = create_user(uname.strip(), pw, role,
                                    created_by=admin["username"])
                st.success(
                    f"User **{uname}** created. "
                    f"Nickname: **{new_u['nickname']}**. "
                    f"ID: `{new_u['user_id']}`"
                )
                st.rerun()

    st.markdown("---")
    st.subheader("All Users")
    users = get_all_users()
    if not users:
        st.caption("No users yet.")
        return

    for u in users:
        nick    = get_display_name(u["user_id"])
        is_self = u["user_id"] == admin["user_id"]
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
            with c1:
                st.markdown(f"**{u['username']}**  —  nickname: `{nick}`")
                st.caption(
                    f"ID: `{u['user_id']}`  ·  "
                    f"Created: {format_ts(u.get('created_at',''), 'Asia/Kolkata')[:12]}  ·  "
                    f"{'⚠️ Must change password' if u.get('must_change_password') else '✅ Password set'}"
                )
            with c2:
                opts     = ["user", "admin"]
                cur_idx  = opts.index(u.get("role", "user"))
                new_role = st.selectbox("Role", opts, index=cur_idx,
                                        key=f"role_{u['user_id']}",
                                        disabled=is_self)
                if not is_self and st.button("Update Role",
                                              key=f"roleb_{u['user_id']}"):
                    set_user_role(u["user_id"], new_role)
                    st.success("Role updated.")
                    st.rerun()
            with c3:
                st.caption("Reset password")
                with st.form(f"rst_{u['user_id']}"):
                    npw = st.text_input("New password", type="password",
                                        key=f"npw_{u['user_id']}")
                    if st.form_submit_button("Reset"):
                        if len(npw) < 6:
                            st.error("Min 6 chars.")
                        else:
                            change_password(u["user_id"], npw)
                            from data.db import force_password_change
                            force_password_change(u["user_id"])
                            st.success("Password reset.")
            with c4:
                if not is_self:
                    if st.button("🗑️", key=f"delu_{u['user_id']}",
                                  help="Delete user"):
                        st.session_state[f"del_u_{u['user_id']}"] = True
            if st.session_state.get(f"del_u_{u['user_id']}"):
                st.warning(f"Delete user **{u['username']}**?")
                cc1, cc2 = st.columns(2)
                if cc1.button("Yes", key=f"deluyes_{u['user_id']}", type="primary"):
                    delete_user(u["user_id"])
                    st.session_state.pop(f"del_u_{u['user_id']}", None)
                    st.rerun()
                if cc2.button("Cancel", key=f"deluno_{u['user_id']}"):
                    st.session_state.pop(f"del_u_{u['user_id']}", None)
                    st.rerun()


# ── Tournaments ───────────────────────────────────────────────────────────────

def _tournaments_tab(user: dict):
    st.subheader("Create Tournament")
    with st.form("create_t"):
        c1, c2  = st.columns(2)
        t_id    = c1.text_input("Tournament ID", placeholder="IPL2026")
        name    = c2.text_input("Name",          placeholder="IPL 2026")
        sport   = c1.selectbox("Sport", [
            "Cricket","Football","Formula 1","Tennis",
            "Basketball","Rugby","Golf","Hockey","Other"])
        s_date  = c2.date_input("Start Date", value=date.today())
        c3, c4  = st.columns(2)
        allowed = c3.number_input("Free Misses Allowed",
                                   min_value=0, max_value=20, value=3)
        penalty = c4.number_input("Penalty Points per Miss",
                                   min_value=0.0, max_value=10.0,
                                   value=1.0, step=0.5)
        st.info(f"Users get **{int(allowed)}** free misses. "
                f"Each extra miss costs **{penalty}** pts.")
        if st.form_submit_button("Create Tournament", type="primary"):
            if not t_id or not name:
                st.error("ID and Name required.")
            else:
                if tournament_id_exists(t_id):
                    st.error(f"Tournament ID `{t_id}` already exists. Choose a unique ID.")
                else:
                    create_tournament({
                        "tournament_id": t_id, "name": name, "sport": sport,
                        "start_date": str(s_date), "allowed_misses": allowed,
                        "penalty_points": penalty, "created_by": user["username"]})
                    st.success(f"Tournament **{name}** created!")
                    st.rerun()

    st.markdown("---")
    st.subheader("Existing Tournaments")
    tournaments = get_tournaments()
    if not tournaments:
        st.caption("No tournaments yet.")
        return

    for t in tournaments:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 2, 2, 1])

            with c1:
                st.markdown(f"**{t['name']}** — {t['sport']}")
                st.caption(
                    f"ID: `{t['tournament_id']}`  ·  "
                    f"Starts: {t['start_date']}  ·  "
                    f"Misses: {t['allowed_misses']}  ·  "
                    f"Penalty: {t['penalty_points']} pts"
                )

            with c2:
                status = t.get("status", "upcoming")
                opts   = ["upcoming", "active", "completed"]
                new_s  = st.selectbox("Status", opts,
                                       index=opts.index(status),
                                       key=f"ts_{t['tournament_id']}")
                if st.button("Update", key=f"tsb_{t['tournament_id']}"):
                    update_tournament_status(t["tournament_id"], new_s)
                    st.rerun()

            with c3:
                ms = get_matches(t["tournament_id"])
                st.metric("Matches", len(ms))

            with c4:
                # Delete tournament
                del_key = f"del_t_{t['tournament_id']}"
                if st.button("🗑️", key=f"delt_{t['tournament_id']}",
                              help="Delete tournament and all data"):
                    st.session_state[del_key] = True

            if st.session_state.get(f"del_t_{t['tournament_id']}"):
                st.error(
                    f"⚠️ Delete **{t['name']}**? "
                    f"This will permanently delete all matches, votes, "
                    f"points and registrations for this tournament."
                )
                cc1, cc2 = st.columns(2)
                if cc1.button("Yes, delete everything",
                               key=f"deltyes_{t['tournament_id']}",
                               type="primary"):
                    delete_tournament(t["tournament_id"])
                    st.session_state.pop(f"del_t_{t['tournament_id']}", None)
                    st.success(f"Tournament **{t['name']}** and all its data deleted.")
                    st.rerun()
                if cc2.button("Cancel", key=f"deltno_{t['tournament_id']}"):
                    st.session_state.pop(f"del_t_{t['tournament_id']}", None)
                    st.rerun()


# ── Matches ───────────────────────────────────────────────────────────────────

def _matches_tab(user: dict):
    ts = get_tournaments()
    if not ts:
        st.warning("Create a tournament first.")
        return

    t_names = [t["name"] for t in ts]
    t_ids   = [t["tournament_id"] for t in ts]
    sel_n   = st.selectbox("Tournament", t_names, key="adm_m_t")
    sel_tid = t_ids[t_names.index(sel_n)]

    tab_a, tab_b = st.tabs(["📤 Bulk Upload CSV", "➕ Add Single Match"])
    with tab_a: _bulk_upload(sel_tid, user)
    with tab_b: _single_form(sel_tid, user)

    st.markdown("---")
    st.subheader(f"Matches — {sel_n}")
    ms = get_matches(sel_tid)
    if not ms:
        st.caption("No matches yet.")
        return

    for m in ms:
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 2, 1])
            with c1:
                scoring = m.get("scoring_mode","ratio")
                poll    = m.get("poll_mode","closed")
                odds    = m.get("fixed_odds","")
                st.markdown(f"**{m['title']}**")
                st.caption(
                    f"`{m['match_id']}`  ·  {m['location']}  ·  "
                    f"{m['match_date']} {m['start_time']} {m['timezone'].split('/')[-1]}  ·  "
                    f"Options: `{m['options']}`  ·  "
                    f"Scoring: **{scoring}**"
                    + (f" @ {odds}" if scoring == "fixed" else "") +
                    f"  ·  Poll: **{poll}**  ·  Status: **{m['status']}**"
                    + (f"  ·  Result: **{m['result']}**" if m.get("result") else "")
                )
            with c2:
                st.caption("🟢 Poll open" if is_voting_open(m) else "🔴 Poll closed")
                votes = get_votes(match_id=m["match_id"])
                if votes:
                    with st.expander(f"👁 Votes ({len(votes)})"):
                        all_u = get_all_users()
                        umap  = {u["user_id"]: get_display_name(u["user_id"])
                                 for u in all_u}
                        for v in votes:
                            dn = umap.get(v["user_id"], v["user_id"])
                            cc1, cc2 = st.columns([3, 1])
                            cc1.markdown(f"**{dn}** → {v['vote']}")
                            if cc2.button("🗑️", key=f"dv_{v['vote_id']}"):
                                delete_vote(v["user_id"], m["match_id"])
                                st.success(f"Vote by {dn} deleted.")
                                st.rerun()
            with c3:
                if st.button("🗑️ Delete", key=f"del_{m['match_id']}"):
                    st.session_state[f"del_m_{m['match_id']}"] = True
            if st.session_state.get(f"del_m_{m['match_id']}"):
                st.warning(f"Delete **{m['title']}**?")
                cc1, cc2 = st.columns(2)
                if cc1.button("Yes", key=f"delmy_{m['match_id']}", type="primary"):
                    delete_match(m["match_id"])
                    st.session_state.pop(f"del_m_{m['match_id']}", None)
                    st.rerun()
                if cc2.button("No", key=f"delmn_{m['match_id']}"):
                    st.session_state.pop(f"del_m_{m['match_id']}", None)
                    st.rerun()


def _bulk_upload(tid: str, user: dict):
    st.markdown("""
**CSV columns:** `match_id, title, location, match_date, start_time, timezone, options, scoring_mode, fixed_odds, poll_mode`

- `scoring_mode`: `ratio` or `fixed`
- `fixed_odds`: winner points when scoring_mode=fixed
- `poll_mode`: `closed` or `open`
- `options`: auto-filled from title if left blank
    """)
    uploaded = st.file_uploader("Upload CSV", type="csv")
    if not uploaded: return
    try:
        df = pd.read_csv(uploaded, dtype=str).fillna("")
        st.dataframe(df, use_container_width=True)
        required = ["match_id","title","location","match_date","start_time","timezone"]
        missing  = [c for c in required if c not in df.columns]
        if missing: st.error(f"Missing columns: {missing}"); return

        errors = []
        for _, row in df.iterrows():
            opts = str(row.get("options","")).strip() or _options_from_title(str(row.get("title","")))
            valid, err = _validate_options(opts)
            if not valid: errors.append(f"`{row['match_id']}`: {err}")
        if errors:
            for e in errors: st.error(e)
            return

        for _, row in df.iterrows():
            try:
                utc = get_match_cutoff_utc(row.to_dict())
                st.caption(f"`{row['match_id']}` closes {utc.strftime('%d %b %Y %H:%M UTC')}")
            except Exception as e:
                st.warning(f"{row['match_id']}: {e}")

        if st.button("Import All", type="primary"):
            rows = []
            for _, row in df.iterrows():
                r = row.to_dict()
                if not r.get("options","").strip():
                    r["options"] = _options_from_title(r.get("title",""))
                if not r.get("scoring_mode","").strip(): r["scoring_mode"] = "ratio"
                if not r.get("poll_mode","").strip():    r["poll_mode"]    = "closed"
                # Normalise time: hh:mm:ss → hh:mm, missing parts default to 00
                r["start_time"] = _parse_time(r.get("start_time","00:00"))
                # Check match ID uniqueness
                if match_id_exists_in_tournament(r["match_id"], tid):
                    st.warning(f"Skipped `{r['match_id']}` — ID already exists.")
                    continue
                rows.append(r)
            bulk_create_matches(tid, rows, user["username"])
            st.success(f"{len(rows)} matches imported!")
            st.rerun()
    except Exception as e:
        st.error(f"CSV error: {e}")


def _single_form(tid: str, user: dict):
    st.markdown("#### Match Details")
    c1, c2   = st.columns(2)
    match_id = c1.text_input("Match ID", placeholder="IPL2026-M001", key="sf_match_id")
    title    = c2.text_input("Title",    placeholder="SRH vs RCB",   key="sf_title")
    location = c1.text_input("Location", placeholder="Hyderabad",    key="sf_location")
    m_date   = c2.date_input("Match Date", value=date.today(),        key="sf_date")
    c3, c4   = st.columns(2)
    s_time   = c3.time_input("Start Time (venue local)", value=time(19, 30), key="sf_time")
    tz       = c4.selectbox("Venue Timezone", COMMON_TIMEZONES, key="sf_tz")

    suggested = _options_from_title(title) if title else ""
    options   = st.text_input(
        "Vote Options (pipe separated, min 2)",
        value=suggested, key="sf_options",
        placeholder="SRH|RCB  or  VER|HAM|LEC|NOR",
        help="Auto-filled from title — edit freely"
    )
    if options:
        valid, err = _validate_options(options)
        if not valid:
            st.error(err)
        else:
            parts = [o.strip() for o in options.split("|") if o.strip()]
            st.success(f"{len(parts)} options: {' · '.join(parts)}")

    st.markdown("#### Scoring & Poll Settings")
    sc1, sc2, sc3 = st.columns(3)
    scoring_mode  = sc1.selectbox(
        "Scoring Mode",
        ["ratio", "fixed"],
        format_func=lambda x: "📊 Ratio (dynamic)" if x == "ratio" else "🎯 Fixed Odds",
        key="sf_scoring"
    )
    fixed_odds = sc2.number_input(
        "Fixed Odds (winner points)",
        min_value=0.1, max_value=100.0, value=2.0, step=0.5,
        key="sf_odds", disabled=(scoring_mode == "ratio"),
        help="Points for correct pickers. Losers -1, missed -penalty → bank."
    )
    poll_mode = sc3.selectbox(
        "Poll Mode",
        ["closed", "open"],
        format_func=lambda x: "🔒 Closed (votes hidden till end)"
                               if x == "closed" else "👁 Open (always visible)",
        key="sf_poll"
    )

    if scoring_mode == "ratio":
        st.info("**Ratio:** Winners share all points lost by losers and penalised missed voters. "
                "Losers = −1 → winner pool. Missed beyond limit = −penalty → winner pool.")
    else:
        st.info(f"**Fixed:** Winners get **+{fixed_odds} pts** each. "
                "Losers = −1 → bank. Missed beyond limit = −penalty → bank.")

    try:
        utc = get_match_cutoff_utc({"match_date": str(m_date),
                                     "start_time": s_time.strftime("%H:%M"),
                                     "timezone": tz})
        st.caption(f"Voting closes: **{utc.strftime('%d %b %Y %H:%M UTC')}**")
    except Exception: pass

    if st.button("Add Match", type="primary", key="sf_submit"):
        if not match_id or not title:
            st.error("ID and Title required.")
        else:
            valid, err = _validate_options(options)
            if not valid:
                st.error(err)
            else:
                if match_id_exists_in_tournament(match_id, tid):
                    st.error(f"Match ID `{match_id}` already exists in this tournament.")
                else:
                    create_match({
                        "match_id": match_id, "tournament_id": tid,
                        "title": title, "location": location,
                        "match_date": str(m_date),
                        "start_time": s_time.strftime("%H:%M"),
                        "timezone": tz, "options": options,
                        "scoring_mode": scoring_mode, "fixed_odds": fixed_odds,
                        "poll_mode": poll_mode, "created_by": user["username"],
                    })
                    st.success(f"Match `{match_id}` added!")
                    st.rerun()


# ── Results ───────────────────────────────────────────────────────────────────

def _recalculate_tournament(sel_tid: str):
    """Thin wrapper around data.points.recalculate_tournament (shared with the API)."""
    return recalculate_tournament(sel_tid)


def _apply_result(match: dict, winner: str, sel_tid: str):
    """
    Shared logic for Save Result and Update Result — delegates to
    data.points.apply_match_result (shared with the API), then renders the
    same UI feedback as before and calls st.rerun() on completion.
    """
    with st.spinner("Calculating points..."):
        outcome = apply_match_result(match["match_id"], sel_tid, winner)

    if outcome["abandoned"]:
        st.warning(
            f"**{match['title']}** has no votes — "
            "marked as abandoned. No points calculated."
        )
    else:
        st.success(
            f"**{winner}** won — {outcome['correct_voters']} correct voter(s). "
            "Points saved."
        )
        if email_configured():
            with st.spinner("Sending emails..."):
                try:
                    send_result_emails(match, winner, sel_tid, outcome["records"])
                    st.toast("📧 Poll results email sent!", icon="✅")
                    st.toast("📧 Leaderboard email sent!", icon="✅")
                except Exception as e:
                    st.warning(f"Email failed: {e}", icon="⚠️")

    st.rerun()


def _results_tab():
    ts = get_tournaments()
    if not ts: st.warning("No tournaments found."); return

    t_names = [t["name"] for t in ts]
    t_ids   = [t["tournament_id"] for t in ts]
    sel_n   = st.selectbox("Tournament", t_names, key="adm_r_t")
    sel_tid = t_ids[t_names.index(sel_n)]

    all_ms     = get_matches(sel_tid)
    if not all_ms: st.info("No matches yet."); return

    pending    = [m for m in all_ms
                  if m["status"] not in ("completed", "abandoned")
                  and not is_voting_open(m)]
    still_open = [m for m in all_ms
                  if m["status"] not in ("completed", "abandoned")
                  and is_voting_open(m)]
    done       = [m for m in all_ms if m["status"] in ("completed", "abandoned")]

    FRAME_H = 400   # scrollable frame height

    # ── Tournament-level Recalculate ──────────────────────────────────────────
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown("**🔄 Recalculate All Points**")
        c1.caption(
            "Recalculates points for every completed match in this tournament "
            "in chronological order. Use after correcting votes or when a "
            "new player joins mid-tournament."
        )
        if c2.button("Recalculate Tournament", type="primary",
                     key="recalc_all", use_container_width=True):
            try:
                with st.spinner(f"Recalculating all matches in {sel_n}..."):
                    ok, ab, err = _recalculate_tournament(sel_tid)
            except RuntimeError as e:
                st.error(str(e))
            else:
                msg = f"Done — {ok} match(es) recalculated"
                if ab: msg += f", {ab} abandoned (no votes)"
                if err: msg += f", {err} error(s)"
                st.success(msg)
                st.rerun()

    # ── Migrate match_players ─────────────────────────────────────────────────
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        c1.markdown("**🗂️ Rebuild match_players**")
        c1.caption(
            "Rebuilds match_players.json for this tournament from scratch: "
            "voted + missed records, quit records preserved, abandoned matches "
            "skipped. Safe to re-run at any time. Use this to inspect or "
            "repair match_players without recalculating points."
        )
        if c2.button("Rebuild match_players", key="run_migration", use_container_width=True):
            try:
                with st.spinner("Rebuilding match_players…"):
                    from data.match_players import rebuild_for_tournament
                    n = rebuild_for_tournament(sel_tid)
            except RuntimeError as e:
                st.error(str(e))
            else:
                st.success(f"Done — {n} record(s) written for {sel_n}.")
                st.rerun()

    st.markdown("")

    # ── 1. Awaiting Result Entry ───────────────────────────────────────────────
    st.subheader("🎯 Awaiting Result Entry")
    st.caption("Poll closed — enter the winner to calculate points.")
    if not pending:
        st.caption("No matches awaiting result.")
    else:
        with st.container(border=True, height=FRAME_H):
            for m in pending:
                opts    = [o.strip() for o in m["options"].split("|") if o.strip()]
                scoring = m.get("scoring_mode", "ratio")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    c1.markdown(f"**{m['title']}**")
                    c1.caption(f"`{m['match_id']}`  ·  {m['match_date']} {m['start_time']}  ·  Scoring: **{scoring}**")
                    winner = c2.selectbox("Winner", opts, key=f"r_{m['match_id']}")
                    if c3.button("Save Result", key=f"rb_{m['match_id']}", type="primary"):
                        _apply_result(m, winner, sel_tid)

    st.markdown("")

    # ── 2. Voting Still Open ──────────────────────────────────────────────────
    st.subheader("⏳ Voting Still Open")
    st.caption("Results cannot be entered until voting closes.")
    if not still_open:
        st.caption("No matches with open voting.")
    else:
        with st.container(border=True, height=FRAME_H):
            for m in still_open:
                scoring = m.get("scoring_mode", "ratio")
                votes   = get_votes(match_id=m["match_id"])
                with st.container(border=True):
                    c1, c2 = st.columns([4, 2])
                    c1.markdown(f"**{m['title']}**")
                    c1.caption(
                        f"`{m['match_id']}`  ·  "
                        f"Closes: {m['start_time']} {m['timezone'].split('/')[-1]}  ·  "
                        f"Scoring: **{scoring}**"
                    )
                    c2.metric("Votes cast", len(votes))

    st.markdown("")

    # ── 3. Update / Correct Result ────────────────────────────────────────────
    st.subheader("✏️ Update / Correct Result")
    st.caption("Change the result for a match — points are recalculated automatically.")
    if not done:
        st.caption("No completed matches.")
    else:
        with st.container(border=True, height=FRAME_H):
            for m in done:
                opts     = [o.strip() for o in m["options"].split("|") if o.strip()]
                cur_res  = m.get("result", "")
                is_aband = m.get("status") == "abandoned" or cur_res == "abandoned"
                cur_idx  = opts.index(cur_res) if cur_res in opts else 0

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])

                    with c1:
                        st.markdown(f"**{m['title']}**")
                        if is_aband:
                            st.caption(
                                f"`{m['match_id']}`  ·  ⛔ Abandoned  ·  "
                                f"Scoring: **{m.get('scoring_mode','ratio')}**"
                            )
                        else:
                            st.caption(
                                f"`{m['match_id']}`  ·  Result: **{cur_res}**  ·  "
                                f"Scoring: **{m.get('scoring_mode','ratio')}**"
                            )

                    new_w   = c2.selectbox("Change to", opts, index=cur_idx,
                                           key=f"corr_{m['match_id']}")
                    changed = new_w != cur_res or is_aband

                    if c3.button("Update Result", key=f"corrb_{m['match_id']}",
                                  type="primary", disabled=not changed):
                        _apply_result(m, new_w, sel_tid)

    st.markdown("")
    st.markdown("---")

    # ── Manual Penalties ─────────────────────────────────────────────────────
    st.markdown("#### 💸 Manual Penalties")
    st.caption(
        "Deduct points from a player manually. "
        "Penalty points flow to the bank. "
        "Does not affect the leaderboard rank — displayed separately below the table."
    )

    penalties = get_penalties(sel_tid)
    all_users = get_all_users()
    umap      = {u["user_id"]: get_display_name(u["user_id"]) for u in all_users}

    # Add penalty form
    with st.container(border=True):
        pc1, pc2, pc3, pc4 = st.columns([3, 2, 4, 2])
        pen_player = pc1.selectbox(
            "Player", [umap[u["user_id"]] for u in all_users],
            key="pen_player_sel"
        )
        pen_uid   = next(u["user_id"] for u in all_users
                         if umap[u["user_id"]] == pen_player)
        pen_pts   = pc2.number_input(
            "Points (positive)", min_value=0.5, step=0.5,
            value=1.0, key="pen_pts_inp"
        )
        pen_reason = pc3.text_input("Reason", key="pen_reason_inp")
        pc4.markdown("<div style='padding-top:24px'></div>", unsafe_allow_html=True)
        if pc4.button("Add Penalty", type="primary",
                      key="pen_add_btn", use_container_width=True):
            if not pen_reason.strip():
                st.error("Reason is required.")
            else:
                add_penalty(sel_tid, pen_uid, pen_pts, pen_reason)
                st.success(f"Penalty of -{pen_pts:.2f} added for **{pen_player}**.")
                st.rerun()

    # Existing penalties list
    if penalties:
        st.markdown("")
        for p in penalties:
            name     = umap.get(p["user_id"], p["user_id"])
            pts_str  = f"-{float(p['points']):.2f}"
            date_str = p.get("created_at", "")[:10]
            pc1, pc2, pc3, pc4, pc5 = st.columns([2, 1, 4, 2, 1])
            pc1.markdown(f"**{name}**")
            pc2.markdown(f"<span style='color:#a01414;font-weight:700'>{pts_str}</span>",
                         unsafe_allow_html=True)
            pc3.caption(p.get("reason", ""))
            pc4.caption(date_str)
            if pc5.button("🗑️", key=f"del_pen_{p['penalty_id']}",
                          help="Delete this penalty"):
                delete_penalty(p["penalty_id"])
                st.rerun()
    else:
        st.caption("No penalties recorded for this tournament.")


# ── Player Quit / Reinstate ───────────────────────────────────────────────────

def _quit_tab():
    st.subheader("🚪 Player Quit / Reinstate")
    st.caption(
        "Mark a player as quit from a specific match, or reinstate them from "
        "a specific match. match_players.json is updated immediately — "
        "run **Recalculate Tournament** in the Results tab afterwards to "
        "apply the change to points."
    )

    ts = get_tournaments()
    if not ts:
        st.warning("No tournaments found.")
        return

    t_names = [t["name"] for t in ts]
    t_ids   = [t["tournament_id"] for t in ts]
    sel_n   = st.selectbox("Tournament", t_names, key="quit_t_sel")
    sel_tid = t_ids[t_names.index(sel_n)]

    all_ms    = get_matches(sel_tid)
    all_users = get_all_users()

    if not all_ms:
        st.info("No matches in this tournament yet.")
        return

    player_status = get_player_quit_status(sel_tid)

    if not player_status:
        st.info("No match_players records yet. Run 'Rebuild match_players' in Results first.")
        return

    # Matches sorted chronologically — used for dropdowns
    import pytz
    from datetime import datetime as _dt

    def _sort_key(m):
        local_tz = pytz.timezone(m.get("timezone", "Asia/Kolkata"))
        local_dt = _dt.strptime(f"{m['match_date']} {m['start_time']}", "%Y-%m-%d %H:%M")
        return local_tz.localize(local_dt)

    sorted_ms   = sorted(all_ms, key=_sort_key)
    match_ids   = [m["match_id"]         for m in sorted_ms]
    match_labels = [_match_ist_label(m)  for m in sorted_ms]

    # ── Player status table ───────────────────────────────────────────────────
    st.markdown("#### Current Player Status")

    umap = {u["user_id"]: get_display_name(u["user_id"]) for u in all_users}

    sorted_uids = sorted(
        player_status.keys(),
        key=lambda uid: (
            0 if player_status[uid]["has_quit_records"] else 1,
            umap.get(uid, uid)
        )
    )

    header_cols = st.columns([3, 4, 1, 1])
    header_cols[0].markdown("**Player**")
    header_cols[1].markdown("**Status**")
    header_cols[2].markdown("**Active**")
    header_cols[3].markdown("**Quit**")
    st.divider()

    for uid in sorted_uids:
        s    = player_status[uid]
        name = umap.get(uid, uid)
        c1, c2, c3, c4 = st.columns([3, 4, 1, 1])
        c1.markdown(f"**{name}**")
        if s["has_quit_records"]:
            c2.markdown(f"🔴 Quit from: `{s['quit_since_label']}`")
        else:
            c2.markdown("🟢 Active")
        c3.markdown(str(s["active_matches"]))
        c4.markdown(str(s["quit_matches"]))

    st.markdown("")
    st.markdown("---")

    # ── Quit action ───────────────────────────────────────────────────────────
    st.markdown("#### Mark Player as Quit")
    st.caption(
        "Sets all match_players records from the selected match onwards "
        "(inclusive, by IST start time) to **quit** status. "
        "Records for earlier matches are unchanged."
    )

    active_uids  = [uid for uid in sorted_uids
                    if player_status[uid]["active_matches"] > 0]
    active_names = [umap.get(uid, uid) for uid in active_uids]

    if not active_uids:
        st.caption("No active players to quit.")
    else:
        with st.container(border=True):
            qc1, qc2, qc3 = st.columns([2, 4, 2])
            quit_name = qc1.selectbox(
                "Player", active_names, key="quit_player_sel"
            )
            quit_uid = active_uids[active_names.index(quit_name)]

            quit_label = qc2.selectbox(
                "Quit from match (IST)", match_labels,
                index=len(match_labels) - 1,   # default: last match
                key="quit_match_sel"
            )
            quit_match_id = match_ids[match_labels.index(quit_label)]

            if qc3.button("Mark as Quit", type="primary",
                          key="quit_btn", use_container_width=True):
                try:
                    with st.spinner("Updating match_players…"):
                        n = quit_player(quit_uid, sel_tid, quit_match_id)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    if n == 0:
                        st.warning(
                            f"No match_players records found for **{quit_name}** "
                            f"at or after the selected match."
                        )
                    else:
                        st.success(
                            f"**{quit_name}** marked as quit from "
                            f"_{quit_label}_ — {n} record(s) updated. "
                            f"Run **Recalculate Tournament** to apply to points."
                        )
                        st.rerun()

    st.markdown("")

    # ── Reinstate action ──────────────────────────────────────────────────────
    st.markdown("#### Reinstate Player")
    st.caption(
        "Removes quit records from the selected match onwards and rebuilds "
        "match_players so those matches become **voted / missed** again. "
        "Earlier quit records are preserved."
    )

    quit_uids  = [uid for uid in sorted_uids
                  if player_status[uid]["has_quit_records"]]
    quit_names = [umap.get(uid, uid) for uid in quit_uids]

    if not quit_uids:
        st.caption("No quit players to reinstate.")
    else:
        with st.container(border=True):
            rc1, rc2, rc3 = st.columns([2, 4, 2])
            reinstate_name = rc1.selectbox(
                "Player", quit_names, key="reinstate_player_sel"
            )
            reinstate_uid = quit_uids[quit_names.index(reinstate_name)]

            # Pre-select the match they quit from
            default_mid   = player_status[reinstate_uid]["quit_from_match_id"]
            default_idx   = (match_ids.index(default_mid)
                             if default_mid in match_ids else 0)

            rejoin_label = rc2.selectbox(
                "Rejoin from match (IST)", match_labels,
                index=default_idx,
                key="reinstate_match_sel"
            )
            rejoin_match_id = match_ids[match_labels.index(rejoin_label)]

            if rc3.button("Reinstate", type="primary",
                          key="reinstate_btn", use_container_width=True):
                try:
                    with st.spinner("Reinstating player and rebuilding match_players…"):
                        n = reinstate_player(reinstate_uid, sel_tid, rejoin_match_id)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    st.success(
                        f"**{reinstate_name}** reinstated from "
                        f"_{rejoin_label}_ — {n} quit record(s) removed, "
                        f"match_players rebuilt. "
                        f"Run **Recalculate Tournament** to apply to points."
                    )
                    st.rerun()

    st.markdown("")
    st.markdown("---")

    # ── Miss Floor ────────────────────────────────────────────────────────────
    st.markdown("#### 🚫 Miss Floor (Knockout Stage)")
    st.caption(
        "Max out every active player's free-miss allowance from a chosen match "
        "onwards, so any miss in the knockout stage is immediately penalised. "
        "Run **Recalculate Tournament** afterwards to apply to points."
    )

    floor_status = get_miss_floor_status(sel_tid)

    if floor_status:
        fmid  = floor_status["from_match_id"]
        fm    = next((m for m in sorted_ms if m["match_id"] == fmid), None)
        flbl  = _match_ist_label(fm) if fm else fmid
        st.info(
            f"✅ Miss floor active from _{flbl}_ — "
            f"{floor_status['player_count']} player(s), "
            f"{floor_status['record_count']} synthetic record(s)."
        )
        if st.button("Remove Miss Floor", key="remove_floor_btn",
                     use_container_width=False):
            try:
                with st.spinner("Removing miss floor…"):
                    n = remove_miss_floor(sel_tid)
            except RuntimeError as e:
                st.error(str(e))
            else:
                st.success(f"Miss floor removed — {n} record(s) deleted. "
                           "Run **Recalculate Tournament** to apply.")
                st.rerun()
    else:
        st.caption("No miss floor active for this tournament.")
        with st.container(border=True):
            fc1, fc2, fc3 = st.columns([2, 4, 2])
            floor_label = fc2.selectbox(
                "Apply from match (IST)", match_labels,
                key="floor_match_sel"
            )
            floor_match_id = match_ids[match_labels.index(floor_label)]
            if fc3.button("Apply Miss Floor", type="primary",
                          key="apply_floor_btn", use_container_width=True):
                try:
                    with st.spinner("Applying miss floor…"):
                        n = apply_miss_floor(sel_tid, floor_match_id)
                except RuntimeError as e:
                    st.error(str(e))
                else:
                    st.success(
                        f"Miss floor applied from _{floor_label}_ — "
                        f"{n} synthetic record(s) written. "
                        "Run **Recalculate Tournament** to apply to points."
                    )
                    st.rerun()
