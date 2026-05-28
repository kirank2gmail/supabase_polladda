# 🏆 SportsPoll

A zero-cost sports polling app built with Streamlit + Google Sheets.

## Features
- Google OAuth login (30-day session cookie — no re-login)
- Multi-tournament support with registration
- N-option voting per match (not just 2 teams)
- Automatic vote deadline enforcement (timezone-aware)
- Vote update allowed until match start time
- Configurable missed-vote penalties per tournament
- Points engine: ratio-based rewards + penalty pool distribution
- Sortable leaderboard with per-match columns, streaks, missed count
- Admin panel: bulk CSV match upload, result entry, points recalculation

---

## Setup Guide

### 1. Google Cloud — OAuth Credentials
1. Go to https://console.cloud.google.com
2. Create project: **SportsPoll**
3. Enable: **Google People API**
4. OAuth Consent Screen → External → Scopes: `email`, `profile`, `openid`
5. Credentials → OAuth 2.0 Client ID → Web Application
6. Authorised redirect URIs:
   - `http://localhost:8501/` (local dev)
   - `https://yourapp.streamlit.app/` (production)
7. Note your `client_id` and `client_secret`

### 2. Google Sheets — Service Account
1. In same GCP project → IAM & Admin → Service Accounts
2. Create service account: `sportspoll-sa`
3. Keys → Add Key → JSON → Download
4. Create a Google Sheet named **SportsPoll** (or your chosen name)
5. Share the sheet with the service account email (Editor access)

### 3. Configure Secrets
```bash
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Fill in your values in secrets.toml
```

Key values to fill:
- `cookie_secret` — any random 32+ char string
- `google_oauth.client_id` — from step 1
- `google_oauth.client_secret` — from step 1
- `google_oauth.redirect_uri` — your app URL
- `gcp_service_account.*` — from the JSON downloaded in step 2
- `app.spreadsheet_name` — name of your Google Sheet
- `app.admin_emails` — list of emails that get admin role

### 4. Install & Run Locally
```bash
pip install -r requirements.txt
streamlit run app.py
```

### 5. Deploy to Streamlit Community Cloud
1. Push to GitHub (exclude `secrets.toml` — add to `.gitignore`)
2. Go to https://share.streamlit.io
3. Connect repo → set main file as `app.py`
4. Add secrets in Streamlit Cloud dashboard (paste contents of secrets.toml)
5. Deploy

---

## Project Structure
```
sportspoll/
├── app.py                  Entry point, routing, navbar
├── requirements.txt
├── .streamlit/
│   └── secrets.toml.template
├── auth/
│   ├── session.py          Cookie-based session (30 day)
│   └── google_oauth.py     Google OAuth flow
├── pages/
│   ├── home.py             Home — ongoing + past matches
│   ├── match.py            Match detail + voting
│   └── leaderboard.py      Sortable leaderboard
├── admin/
│   └── dashboard.py        Tournament/match/result management
├── data/
│   ├── sheets.py           Google Sheets read/write layer
│   └── points.py           Points calculation engine
└── utils/
    ├── timezone.py         Timezone conversion helpers
    └── streaks.py          Win/loss streak + leaderboard builder
```

---

## Google Sheets Structure (auto-created on first run)

| Sheet | Columns |
|---|---|
| users | user_id, name, email, picture_url, role, timezone, created_at |
| tournaments | tournament_id, name, sport, start_date, status, allowed_misses, penalty_points, created_by, created_at |
| registrations | reg_id, user_id, tournament_id, registered_at |
| matches | match_id, tournament_id, title, location, match_date, start_time, timezone, options, status, result, created_by, created_at |
| votes | vote_id, user_id, match_id, tournament_id, vote, voted_at, updated_at, update_count |
| points | point_id, user_id, match_id, tournament_id, base_points, penalty_points, bonus_points, total_points, note, calculated_at |

---

## Match CSV Format (for bulk upload)
```csv
match_id,title,location,match_date,start_time,timezone,options
IPL2026-M001,SRH vs RCB,Hyderabad,2026-05-24,19:30,Asia/Kolkata,SRH|RCB
F12026-R001,Monaco GP,Monaco,2026-05-26,14:00,Europe/Monaco,VER|HAM|LEC|NOR|SAI
EPL-M001,Arsenal vs Chelsea,London,2026-08-16,15:00,Europe/London,Arsenal|Chelsea
```

---

## Points Formula

```
winner_pts  = loser_votes / winner_votes   (base ratio)
            + penalty_pool / winner_votes   (bonus from missed voters)

loser_pts   = 0
missed_pts  = 0                            (if within free miss allowance)
            = -penalty_points              (if beyond allowance)

penalty_pool = count(penalised missed) × tournament.penalty_points
```

---

## .gitignore
```
.streamlit/secrets.toml
__pycache__/
*.pyc
.env
```
