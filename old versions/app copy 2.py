import time
import streamlit as st
from supabase import create_client
from supabase_auth.errors import AuthApiError

st.set_page_config(page_title="Nets Booking", layout="centered")

# -------------------------
# SUPABASE CLIENT
# -------------------------
supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

# -------------------------
# SESSION STATE INIT
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "session" not in st.session_state:
    st.session_state.session = None
if "otp_last_sent" not in st.session_state:
    st.session_state.otp_last_sent = 0.0

# -------------------------
# HYDRATE SESSION FROM ?code=
# Must run early, before UI decisions
# -------------------------
qp = st.query_params
if st.session_state.user is None and "code" in qp:
    code = qp["code"]
    try:
        res = supabase.auth.exchange_code_for_session(code)

        st.session_state.session = res.session
        st.session_state.user = res.user

        # Ensure subsequent queries carry auth for RLS
        supabase.auth.set_session(res.session.access_token, res.session.refresh_token)

        # Clear the code so we don't exchange again on reruns
        st.query_params.clear()
        st.rerun()

    except Exception as e:
        st.error(f"Authentication failed while exchanging code: {e}")
        st.stop()

# -------------------------
# UI
# -------------------------
st.title("🏏 Nets Booking")

# -------------------------
# LOGIN UI (magic link)
# -------------------------
if st.session_state.user is None:
    st.subheader("Login (Magic Link)")

    email = st.text_input("Email address", placeholder="you@example.com")

    cooldown_s = 30
    can_send = (time.time() - st.session_state.otp_last_sent) > cooldown_s

    if st.button("Send magic link", disabled=not can_send) and email:
        try:
            st.session_state.otp_last_sent = time.time()
            supabase.auth.sign_in_with_otp(
                {
                    "email": email,
                    "options": {
                        # Local dev redirect (change this when deployed)
                        "email_redirect_to": "http://localhost:8501"
                    },
                }
            )
            st.success("Magic link sent. Check your email and click the link.")
        except AuthApiError as e:
            msg = str(e)
            if "only request this after" in msg.lower():
                st.warning("Too many requests. Wait ~30 seconds, then try again.")
            else:
                st.error(f"Login error: {msg}")

        st.stop()

    if not can_send:
        remaining = int(cooldown_s - (time.time() - st.session_state.otp_last_sent))
        st.info(f"Please wait {remaining}s before requesting another link.")

    st.info("After you click the email link, you'll land back here and be logged in.")
    st.stop()

# -------------------------
# LOGOUT
# -------------------------
with st.sidebar:
    st.write(f"✅ Logged in as: **{st.session_state.user.email}**")
    if st.button("Logout"):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.user = None
        st.session_state.session = None
        st.rerun()

# -------------------------
# Helper: fetch my bookings (confirmed only)
# -------------------------
def get_my_confirmed_bookings():
    r = (
        supabase.table("bookings")
        .select("id, session_id, status, created_at")
        .eq("status", "confirmed")
        .execute()
    )
    return r.data or []

def cancel_booking(booking_id: int):
    # RLS allows user to update their own rows
    supabase.table("bookings").update(
        {"status": "cancelled", "cancelled_at": "now()"}  # cancelled_at will be set by DB? We'll set in SQL below instead.
    ).eq("id", booking_id).execute()


# -------------------------
# Fix: cancelled_at should be set with a proper timestamp
# We'll do it in python:
# -------------------------
from datetime import datetime, timezone
def cancel_booking(booking_id: int):
    supabase.table("bookings").update(
        {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", booking_id).execute()


# -------------------------
# MAIN: Sessions + Booking
# -------------------------
st.subheader("Available sessions")

sessions_resp = (
    supabase.table("session_availability")
    .select("*")
    .order("start_at")
    .execute()
)

sessions = sessions_resp.data or []
if not sessions:
    st.warning("No sessions found.")
    st.stop()

my_bookings = get_my_confirmed_bookings()
my_session_ids = {b["session_id"] for b in my_bookings}

for s in sessions:
    session_id = s["id"]
    slots_remaining = s["slots_remaining"]
    capacity = s["capacity"]
    start_at = s["start_at"]
    end_at = s["end_at"]
    location = s.get("location") or ""
    notes = s.get("notes") or ""

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.write(f"**{start_at} → {end_at}**")
        meta = " | ".join([x for x in [location, notes] if x])
        if meta:
            st.caption(meta)
        st.caption(f"Slots remaining: **{slots_remaining} / {capacity}**")

    with col2:
        already_booked = session_id in my_session_ids

        if already_booked:
            st.button("Booked ✅", disabled=True, key=f"booked_{session_id}")
        else:
            if st.button("Book", disabled=(slots_remaining <= 0), key=f"book_{session_id}"):
                try:
                    # IMPORTANT: booking must go through the capacity function
                    supabase.rpc("book_session", {"p_session_id": session_id}).execute()
                    st.success("Booked!")
                    st.rerun()
                except Exception as e:
                    msg = str(e).lower()
                    if "session_full" in msg:
                        st.warning("Session is full.")
                    elif "duplicate" in msg or "unique" in msg:
                        st.warning("You already have a booking for this session.")
                    else:
                        st.error(f"Booking failed: {e}")

    with col3:
        if session_id in my_session_ids:
            # Find booking id for this session
            booking_id = next(b["id"] for b in my_bookings if b["session_id"] == session_id)
            if st.button("Cancel", key=f"cancel_{session_id}"):
                try:
                    cancel_booking(booking_id)
                    st.success("Cancelled.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Cancel failed: {e}")

st.divider()

# -------------------------
# MY BOOKINGS
# -------------------------
st.subheader("My bookings")

my_bookings = get_my_confirmed_bookings()
if not my_bookings:
    st.info("No bookings yet.")
else:
    # Join session info for display
    # (simple approach: map from sessions we already have)
    session_map = {s["id"]: s for s in sessions}

    for b in my_bookings:
        s = session_map.get(b["session_id"])
        if s:
            st.write(f"✅ **{s['start_at']}**  |  {s.get('location') or ''}")
        else:
            st.write(f"✅ Session ID: {b['session_id']}")
