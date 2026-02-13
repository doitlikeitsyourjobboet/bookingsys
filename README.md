# Nets Booking

A Streamlit app for managing training session bookings backed by Supabase.

## Features
- Email-based registration and booking
- Admin dashboard for approvals, sessions, and bookings
- Team fixture confirmations (Plucky and Unabombers)
- Supabase-backed storage

## Local Setup
1. Create and activate a virtual environment.
2. Install dependencies.
3. Add Streamlit secrets.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` with your Supabase and admin values:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
ADMIN_PASSWORD = "change-me"
# Optional: enable debug toggles
# DEBUG_MODE = true
```

Run the app:

```powershell
streamlit run Home.py
```

Run BDD tests:

```powershell
pip install -r requirements-dev.txt
pytest
```

## Deploy to Streamlit Cloud
1. Push this repo to GitHub.
2. In Streamlit Cloud, create a new app from the repo.
3. Set the main file path to `Home.py`.
4. Add the same keys above to **App settings > Secrets**.

## Notes
- `.streamlit/secrets.toml` is ignored by Git to prevent accidental leaks.
- To enable debug toggles in the UI, set `DEBUG_MODE = true` in Streamlit secrets.

## Enable Fixture Tables
To support `3_PluckyFixtures.py` and `4_UnabombersFixtures.py`, run:

```sql
-- Copy and run the SQL from:
-- supabase/fixtures_schema.sql
```

In Supabase SQL Editor, paste the contents of `supabase/fixtures_schema.sql` and execute it.

## Enable Profile Fields (Optional but recommended)
To persist profile preferences (including team affiliation, batting and bowling style), bio, and profile photo data, add these columns in Supabase SQL editor:

```sql
alter table public.registrations
  add column if not exists preference text
  check (preference in ('bowling', 'batting', 'both'))
  default 'both';

alter table public.registrations
  add column if not exists team_affiliation text
  check (team_affiliation in ('plucky', 'unabombers'));

alter table public.registrations
  add column if not exists batting_preference text
  check (batting_preference in ('orthodox', 'slogger'));

alter table public.registrations
  add column if not exists bowling_preference text
  check (bowling_preference in ('fast', 'slow', 'right_arm', 'left_arm', 'off_spin', 'leg_spin'));

alter table public.registrations
  add column if not exists bio text;

alter table public.registrations
  add column if not exists profile_photo_data text;
```
