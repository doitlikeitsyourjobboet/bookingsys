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
# HELPERS
# --------------------------------------------------
@st.cache_data(ttl=30)
def get_email_status(email):
    allowed = (
        supabase.table("allowed_emails")
        .select("email")
        .eq("email", email)
        .execute()
        .data
    )

    registration = (
        supabase.table("registrations")
        .select("id, name, status")
        .eq("email", email)
        .execute()
        .data
    )

    return allowed, registration


def get_attendee_names_for_session(session_id: int):
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
    names.sort()

    return names


def cancel_booking_email(booking_id: int):
    supabase.table("bookings_email").update(
        {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        }
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
# INLINE REGISTRATION
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
if allowed:
    st.sidebar.success("✅ Approved member")

elif registration:
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

if not sessions:
    st.warning("No sessions found.")
    st.stop()

# Get ALL bookings for this email
my_bookings = (
    supabase.table("bookings_email")
    .select("id, session_id")
    .eq("email", email)
    .eq("status", "confirmed")
    .execute()
    .data
) or []

# Map session_id → booking_id
my_bookings_by_session = {
    b["session_id"]: b["id"] for b in my_bookings
}

# --------------------------------------------------
# UI
# --------------------------------------------------
st.subheader("Available sessions")

for s in sessions:
    session_id = s["id"]
    slots_remaining = s["slots_remaining"]
    capacity = s["capacity"]

    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.markdown(f"### {s.get('notes') or 'Net Session'}")
        st.caption(
            f"{s['start_at']} · {s.get('location') or ''}"
        )
        st.caption(f"Slots: **{slots_remaining} / {capacity}**")

    with col2:
        if session_id in my_bookings_by_session:
            st.button(
                "Booked ✅",
                disabled=True,
                key=f"booked_{session_id}",
            )
        else:
            if st.button(
                "Book",
                disabled=slots_remaining <= 0,
                key=f"book_{session_id}",
            ):
                supabase.rpc(
                    "book_session_email",
                    {
                        "p_session_id": session_id,
                        "p_email": email,
                    },
                ).execute()
                st.cache_data.clear()
                st.rerun()

    with col3:
        if session_id in my_bookings_by_session:
            if st.button(
                "Cancel",
                key=f"cancel_{session_id}",
            ):
                cancel_booking_email(my_bookings_by_session[session_id])
                st.cache_data.clear()
                st.rerun()

    attendees = get_attendee_names_for_session(session_id)

    with st.expander(f"👥 Attendees ({len(attendees)})"):
        if not attendees:
            st.info("No one booked yet.")
        else:
            my_name = registration[0]["name"]
            for n in attendees:
                if n == my_name:
                    st.markdown(f"- **👉 {n} (You)**")
                else:
                    st.write(f"- {n}")

# --------------------------------------------------
# MY BOOKINGS
# --------------------------------------------------
st.divider()
st.subheader("My bookings")

if not my_bookings:
    st.info("No bookings yet.")
else:
    for b in my_bookings:
        s = next((x for x in sessions if x["id"] == b["session_id"]), None)
        if s:
            st.write(f"✅ **{s.get('notes')}** — {s['start_at']}")
