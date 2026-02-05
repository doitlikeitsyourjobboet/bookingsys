##we are now public

import streamlit as st
from supabase import create_client
from datetime import datetime, timezone

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Nets Booking", layout="wide")

def _has_secret(key: str) -> bool:
    return key in st.secrets


REQUIRED_SECRETS = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]

missing = [k for k in REQUIRED_SECRETS if not _has_secret(k)]
if missing:
    st.error("Missing required configuration.")
    st.code("\n".join(missing))
    st.info(
        "For local dev: add them to `.streamlit/secrets.toml`\n"
        "For Streamlit Cloud: App → Settings → Secrets"
    )
    st.stop()


def _secret_bool(key: str, default: bool = False) -> bool:
    try:
        value = st.secrets[key]
    except Exception:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

st.subheader("Kings Winter Nets ")
st.text("🏏🚀🏏🚀🏏🚀🏏🚀🍺🍺")
st.caption("Book your spot for our winter net sessions!")

DEBUG = False
if _secret_bool("DEBUG_MODE"):
    DEBUG = st.sidebar.checkbox("Debug mode", value=False)

if DEBUG and st.session_state.get("last_debug"):
    st.info("Last action debug")
    st.code(st.session_state.last_debug, language="text")

# Handle logout before any widgets that depend on session state.
if st.session_state.get("do_logout"):
    st.session_state["email"] = ""
    st.session_state.pop("last_debug", None)
    st.session_state.pop("allowed_sync_attempted", None)
    st.session_state.pop("just_registered", None)
    st.session_state.pop("do_logout", None)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
#@st.cache_data(ttl=30)
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
    return (
        supabase.table("bookings_email")
        .update(
            {
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", booking_id)
        .eq("status", "confirmed")  # important safety guard
        .execute()
    )


def allow_email(email_addr: str, name: str):
    return supabase.table("allowed_emails").upsert(
        {"email": email_addr, "notes": f"Auto-approved ({name})"}
    ).execute()


def parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _day_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def fmt_date(dt: datetime) -> str:
    day = dt.day
    return f"{day}{_day_suffix(day)} {dt.strftime('%b %Y')}"


def fmt_time(dt: datetime) -> str:
    return dt.strftime("%I:%M%p").lstrip("0").lower()


def fmt_start(start: str) -> str:
    dt = parse_iso(start)
    return f"{fmt_date(dt)} @{fmt_time(dt)}"


def is_past(dt: datetime) -> bool:
    if dt.tzinfo is None:
        return dt < datetime.now()
    return dt < datetime.now(timezone.utc)


def _resp_summary(resp) -> str:
    parts = []
    for attr in ("status_code", "status", "error", "count"):
        if hasattr(resp, attr):
            parts.append(f"{attr}={getattr(resp, attr)}")
    data = getattr(resp, "data", None)
    if data is not None:
        parts.append(f"data={data}")
    return "\n".join(parts) if parts else repr(resp)


def _debug_action(action: str, responses, context: str = ""):
    if not DEBUG:
        return
    lines = [f"Action: {action}"]
    if context:
        lines.append(f"Context: {context}")
    for i, resp in enumerate(responses, 1):
        lines.append(f"\nResponse {i}:\n{_resp_summary(resp)}")
    st.session_state.last_debug = "\n".join(lines)


# --------------------------------------------------
# EMAIL ENTRY
# --------------------------------------------------
email_input = st.text_input(
    "Your username / email address",
    placeholder="you@example.com",
    key="email",
)
email = email_input.strip().lower()

if not email:
    st.info("Enter your email to continue.")
    st.stop()

allowed, registration = get_email_status(email)

# --------------------------------------------------
# POST-REGISTER HANDOFF
# --------------------------------------------------
if st.session_state.get("just_registered"):
    st.success("Thanks! You're approved and can book now.")
    if st.button("Book Now"):
        st.session_state.pop("just_registered", None)
        st.rerun()
    st.stop()

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

        try:
            resp_reg = supabase.table("registrations").insert(
                {
                    "name": name,
                    "email": email,
                    "status": "approved",
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }
            ).execute()
        except Exception as exc:
            if DEBUG:
                st.error("Registration failed")
                st.code(str(exc))
            st.error("Registration failed. Please try again.")
            st.stop()

        try:
            resp_allow = allow_email(email, name)
        except Exception as exc:
            if DEBUG:
                st.error("Allow-list update failed")
                st.code(str(exc))
            st.error("Registered, but we couldn't enable booking for your email yet.")
            st.stop()

        _debug_action(
            "register_and_allow",
            [resp_reg, resp_allow],
            context=f"email={email}",
        )

        st.cache_data.clear()
        st.session_state["just_registered"] = True
        st.rerun()

    st.stop()

# --------------------------------------------------
# STATUS GATE
# --------------------------------------------------
if allowed:
    welcome_name = registration[0]["name"] if registration else "member"
    st.sidebar.success(f"Welcome, {welcome_name}")
    if st.sidebar.button("Log out"):
        st.session_state["do_logout"] = True
        st.rerun()

elif registration:
    status = registration[0]["status"]

    if status == "approved":
        if not allowed and not st.session_state.get("allowed_sync_attempted"):
            st.session_state["allowed_sync_attempted"] = True
            try:
                resp = allow_email(email, registration[0]["name"])
                _debug_action(
                    "allow_email",
                    [resp],
                    context=f"email={email}",
                )
                st.cache_data.clear()
                st.rerun()
            except Exception as exc:
                if DEBUG:
                    st.error("Auto-allow failed")
                    st.code(str(exc))
                st.error("We couldn't enable booking for your email yet.")
                st.stop()
        st.sidebar.success(f"Welcome, {registration[0]['name']}")
        if st.sidebar.button("Log out"):
            st.session_state["do_logout"] = True
            st.rerun()

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
# MY BOOKINGS
# --------------------------------------------------
st.subheader("My bookings")

if not my_bookings:
    st.info("No bookings yet.")
else:
    booked = []
    for b in my_bookings:
        s = next((x for x in sessions if x["id"] == b["session_id"]), None)
        if s:
            start_dt = parse_iso(s["start_at"])
            booked.append((start_dt, s))

    for start_dt, s in sorted(booked, key=lambda x: x[0]):
        line = f"✅ **{s.get('notes')}** — {fmt_start(s['start_at'])}"
        if is_past(start_dt):
            st.markdown(f"~~{line}~~")
        else:
            st.markdown(line)

st.divider()

# --------------------------------------------------
# UI
# --------------------------------------------------
st.subheader("Book Available Sessions")

for i, s in enumerate(sessions):
    session_id = s["id"]
    slots_remaining = s["slots_remaining"]
    capacity = s["capacity"]

    col1, col2, col3, col4 = st.columns([1, 0.5, 0.5, 3])

    with col1:
        st.markdown(f"##### {s.get('notes') or 'Net Session'}")
        location = s.get("location") or ""
        start_line = fmt_start(s["start_at"])
        line = f"{start_line} - {location}" if location else start_line
        st.markdown(f"###### {line}")
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
                try:
                    resp = supabase.rpc(
                        "book_session_email",
                        {
                            "p_session_id": session_id,
                            "p_email": email,
                        },
                    ).execute()
                    _debug_action(
                        "book_session_email",
                        [resp],
                        context=f"session_id={session_id} email={email}",
                    )
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    if DEBUG:
                        st.session_state.last_debug = (
                            "Action: book_session_email\n"
                            f"Context: session_id={session_id} email={email}\n\n"
                            f"Error:\n{exc}"
                        )
                    if "email_not_allowed" in str(exc):
                        st.error("Booking failed: your email is not allowed yet.")
                    else:
                        st.error("Booking failed. Please try again.")

    with col3:
        booking_id = my_bookings_by_session.get(session_id)

        if booking_id:
            if st.button("Cancel", key=f"cancel_{session_id}"):
                resp = cancel_booking_email(booking_id)
                _debug_action(
                    "cancel_booking_email",
                    [resp],
                    context=f"booking_id={booking_id} session_id={session_id} email={email}",
                )
                st.toast("Booking cancelled", icon="🗑️")
                st.cache_data.clear()
                st.rerun()

    attendees = get_attendee_names_for_session(session_id)
    my_name = registration[0]["name"] if registration else None

    with st.expander(f"👥 Attendees ({len(attendees)})"):
        if not attendees:
            st.info("No one booked yet.")
        else:
            for n in attendees:
                if my_name and n == my_name:
                    st.markdown(f"- **👉 {n} (You)**")
                else:
                    st.write(f"- {n}")
    if i < len(sessions) - 1:
        st.divider()

