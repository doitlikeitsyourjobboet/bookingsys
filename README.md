# Nets Booking

A Streamlit app for managing training session bookings backed by Supabase.

## Features
- Email-based registration and booking
- Admin dashboard for approvals, sessions, and bookings
- Team fixture confirmations (Plucky M's and Unabombers)
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

## Enable Profile Fields (Copy/Paste for Supabase)
Paste this whole script into Supabase SQL Editor and run it once:

```sql
alter table public.registrations
  add column if not exists preference text default 'both',
  add column if not exists team_affiliation text,
  add column if not exists batting_preference text,
  add column if not exists bowling_preference text,
  add column if not exists bio text,
  add column if not exists profile_photo_data text,
  add column if not exists player_id uuid,
  add column if not exists full_name text,
  add column if not exists nickname text,
  add column if not exists date_of_birth date,
  add column if not exists batting_hand text,
  add column if not exists batting_style_traits text,
  add column if not exists preferred_batting_position integer,
  add column if not exists bowling_arm text,
  add column if not exists bowling_traits text,
  add column if not exists preferred_overs_phase text,
  add column if not exists primary_position text;

alter table public.registrations
  drop constraint if exists registrations_preference_check,
  drop constraint if exists registrations_team_affiliation_check,
  drop constraint if exists registrations_batting_preference_check,
  drop constraint if exists registrations_bowling_preference_check,
  drop constraint if exists registrations_batting_hand_check,
  drop constraint if exists registrations_bowling_arm_check,
  drop constraint if exists registrations_preferred_batting_position_check,
  drop constraint if exists registrations_preferred_overs_phase_check,
  drop constraint if exists registrations_primary_position_check;

update public.registrations
set team_affiliation = null
where team_affiliation is not null
  and btrim(team_affiliation) = '';

alter table public.registrations
  add constraint registrations_preference_check
    check (preference in ('bowling', 'batting', 'both')),
  add constraint registrations_team_affiliation_check
    check (
      team_affiliation is null
      or team_affiliation ~ '^(plucky|unabombers|other)(, ?(plucky|unabombers|other))*$'
    ),
  add constraint registrations_batting_preference_check
    check (batting_preference in (
      'opener',
      'top_order',
      'middle_order',
      'finisher',
      'all_rounder',
      'wicketkeeper',
      'tailender'
    )),
  add constraint registrations_bowling_preference_check
    check (bowling_preference in (
      'fast',
      'fast_medium',
      'medium_fast',
      'medium',
      'slow_medium',
      'off_spin',
      'leg_spin',
      'left_arm_orthodox',
      'left_arm_wrist_spin',
      'mystery_spin'
    )),
  add constraint registrations_batting_hand_check
    check (batting_hand in ('right', 'left')),
  add constraint registrations_bowling_arm_check
    check (bowling_arm in ('right', 'left')),
  add constraint registrations_preferred_batting_position_check
    check (preferred_batting_position between 1 and 11),
  add constraint registrations_preferred_overs_phase_check
    check (preferred_overs_phase in ('powerplay', 'middle', 'death')),
  add constraint registrations_primary_position_check
    check (
      primary_position is null
      or primary_position ~ '^(Slip|Gully|Point|Cover|Mid-Off|Mid-On|Mid-Wicket|Fine Leg|Third Man|Long On|Long Off|Wicketkeeper)(, ?(Slip|Gully|Point|Cover|Mid-Off|Mid-On|Mid-Wicket|Fine Leg|Third Man|Long On|Long Off|Wicketkeeper))*$'
    );
```

`team_affiliation`, `batting_style_traits`, `bowling_traits`, and `primary_position` are stored as comma-separated values.
