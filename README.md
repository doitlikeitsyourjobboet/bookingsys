# Nets Booking

A Streamlit app for managing training session bookings backed by Supabase.

## Features
- Email-based registration and booking
- Admin dashboard for approvals, sessions, and bookings
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
