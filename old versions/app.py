import streamlit as st
from supabase import create_client
from datetime import datetime, timezone

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Nets Booking", layout="centered")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

st.title("🏏 Nets Booking")

# --------------------------------------------------
# FORMATTERS
# --------------------------------------------------
def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d/%b/%Y").upper()

def fmt_time(dt: datetime) -> str:
    # Windows-safe: strip leading zero manually
    return dt.strftime("%I:%M%p").lstrip("0").lower()

def fmt_session_range(start: str, end: str) -> str:
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    return f"{fmt_date(s)} · {fmt_time(s)} – {fmt_time(e)}"


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
@st.cache_data(ttl=30)
def get_email_status(email):
    allowed = supabase.table("allowed_emails").select("email").eq("email", email).execute().data
    registration = supabase.table("registrations").select("id, name, status").eq("email", email).execute().data
    return allowed, registration


def get_attendee_names_for_session(session_id):
    bookings = (
        supabase.table("bookings_email")
        .select("email")
        .eq("session_id", session_id)
        .eq("status", "confirmed")
        .execute()
        .data
    ) or []

    if not bookings:
        return []

    emails = [b["email"] for b in bookings]

    regs = (
        supabase.table("registrations")
        .select("name, email")
        .in_("email", emails)
        .execute()
        .data
    ) or []

    email_to_name = {r["email"]: r["name"] for r in regs}
    names = [email_to_name.get(e, "Unknown") for e in emails]
    return sorted(names)


def cancel_booking_email(booking_id):
    supabase.table("bookings_email").update(
        {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", booking_id).execute()


# --------------------------------------------------
# EMAIL ENTRY
# --------------------------------------------------
email = st.text_input("Your email address", placeholder="you@example.com").strip().lower()

if not email:
    st.info("Enter your email to continue.")
    st.stop()

allowed, registration = get_email_status(email)

# --------------------------------------------------
# REGISTRATION INLINE
# --------------------------------------------------
if not allowed and not registration:
    st.subheader("📝 First time here? Register")

    name = st.text_input("Full name")

    if st.button("Register"):
        if not name:
            st.warning("Please enter your full name.")
            st.stop()

        supabase.table("registrations").insert(
            {"name": name, "email": email}
        ).execute()

        st.cache_data.clear()
        st.success("Thanks! Your registration is pending approval.")
        st.stop()

    st.stop()

# --------------------------------------------------
# STATUS GATE
# --------------------------------------------------
if registration:
    status = registration[0]["status"]
    if status == "pending":
        st.warning("⏳ Your registration is pending approval.")
        st.stop()
    if status == "rejected":
        st.error("❌ Your registration was rejected.")
        st.stop()

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
sessions = (
    supabase.table("session_availability")
    .select("*")
    .order("start_at")
    .execute()
    .data
) or []

my_bookings = (
    supabase.table("bookings_email")
    .select("id, session_id")
    .eq("email", email)
    .eq("status", "confirmed")
    .execute()
    .data
) or []

my_session_ids = {b["session_id"] for b in my_bookings}

# --------------------------------------------------
# UI
# --------------------------------------------------
st.subheader("Available sessions")

for s in sessions:
    header = s.get("notes") or "Training Session"
    date_line = fmt_session_range(s["start_at"], s["end_at"])

    st.markdown(f"### {header}")
    st.caption(date_line)

    st.caption(
        f"{s.get('location','')} · "
        f"Slots: **{s['confirmed_count']} / {s['capacity']}**"
    )

    c1, c2 = st.columns([1, 1])

if s["id"] in my_session_ids:
    c1.button(
        "Booked ✅",
        disabled=True,
        key=f"booked_{s['id']}",
    )

    booking_id = next(
        b["id"] for b in my_bookings if b["session_id"] == s["id"]
    )

    if c2.button(
        "Cancel",
        key=f"cancel_{s['id']}",
    ):
        cancel_booking_email(booking_id)
        st.cache_data.clear()
        st.rerun()
else:
    if c1.button(
        "Book",
        disabled=s["slots_remaining"] <= 0,
        key=f"book_{s['id']}",
    ):
        supabase.rpc(
            "book_session_email",
            {"p_session_id": s["id"], "p_email": email},
        ).execute()
        st.cache_data.clear()
        st.rerun()


    attendees = get_attendee_names_for_session(s["id"])
    with st.expander(f"👥 Attendees ({len(attendees)})"):
        for n in attendees:
            if registration and n == registration[0]["name"]:
                st.markdown(f"- **👉 {n} (You)**")
            else:
                st.write(f"- {n}")

    st.divider()
