##we are now public v2.6

import streamlit as st
from supabase import create_client
from streamlit.errors import StreamlitAPIException
from datetime import datetime, timezone
import time
from booking_rules import (
    AUTH_EMAIL_INPUT_KEY,
    AUTH_EMAIL_KEY,
    EMAIL_REQUIRED_MESSAGE,
    evaluate_email_form,
    booking_failure_message,
    format_my_booking_line,
    normalize_email,
    is_valid_email,
    registration_status_message,
)
from app_nav import (
    TEAM_AFFILIATION_SESSION_KEY,
    render_compact_nav,
    render_logout_footer,
    sync_team_affiliation,
)

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Winter Nets",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def _has_secret(key: str) -> bool:
    return key in st.secrets


REQUIRED_SECRETS = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]

missing = [k for k in REQUIRED_SECRETS if not _has_secret(k)]
if missing:
    st.error("Missing required configuration.")
    st.code("\n".join(missing))
    st.info(
        "For local dev: add them to `.streamlit/secrets.toml`\n"
        "For Streamlit Cloud: App -> Settings -> Secrets"
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

render_compact_nav("winter_nets")
st.subheader("Kings Winter Nets")
st.text("Winter cricket nets are open for booking.")
st.caption("Book your spot for our winter net sessions!")

DEBUG = _secret_bool("DEBUG_MODE")

if DEBUG and st.session_state.get("last_debug"):
    st.info("Last action debug")
    st.code(st.session_state.last_debug, language="text")

def _set_state_safe(key: str, value, user_message: str | None = None) -> bool:
    try:
        st.session_state[key] = value
        return True
    except StreamlitAPIException as exc:
        if DEBUG:
            st.error(f"Session state update failed for key: {key}")
            st.code(str(exc))
        st.warning(
            user_message
            or "We hit a temporary session issue. Please refresh and try again."
        )
        return False


def _normalize_email(raw: str) -> str:
    return normalize_email(raw)


def _is_valid_email(email: str) -> bool:
    return is_valid_email(email)


def _execute_query(
    query,
    action: str,
    user_message: str,
    *,
    show_error: bool = True,
    custom_error_message=None,
):
    try:
        return query.execute()
    except Exception as exc:
        if DEBUG:
            st.session_state.last_debug = f"Action: {action}\n\nError:\n{exc}"
            st.error(f"{action} failed")
            st.code(str(exc))
        if show_error:
            if callable(custom_error_message):
                st.error(custom_error_message(exc))
            else:
                st.error(user_message)
        return None


def _get_auth_email() -> str:
    value = st.session_state.get(AUTH_EMAIL_KEY)
    if isinstance(value, str):
        return _normalize_email(value)
    return ""

# Handle logout before any widgets that depend on session state.
if st.session_state.get("do_logout"):
    _set_state_safe(AUTH_EMAIL_KEY, "")
    _set_state_safe(AUTH_EMAIL_INPUT_KEY, "")
    st.session_state.pop("logged_in", None)
    st.session_state.pop("last_debug", None)
    st.session_state.pop("allowed_sync_attempted", None)
    st.session_state.pop("just_registered", None)
    st.session_state.pop("welcome_name", None)
    st.session_state.pop(TEAM_AFFILIATION_SESSION_KEY, None)
    st.session_state.pop("do_logout", None)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
#@st.cache_data(ttl=30)
def get_email_status(email):
    allowed_resp = _execute_query(
        supabase.table("allowed_emails")
        .select("email")
        .eq("email", email),
        action="load_allowed_email",
        user_message="We couldn't verify your access right now. Please try again.",
    )
    if allowed_resp is None:
        return None, None

    registration_resp = _execute_query(
        supabase.table("registrations")
        .select("*")
        .eq("email", email),
        action="load_registration",
        user_message="We couldn't check your registration status right now. Please try again.",
    )
    if registration_resp is None:
        return None, None

    return (allowed_resp.data or []), (registration_resp.data or [])


def get_registration_by_name(username: str):
    clean_username = username.strip()
    if not clean_username:
        return []

    name_resp = _execute_query(
        supabase.table("registrations")
        .select("id, name, status, email")
        .ilike("name", clean_username),
        action="load_registration_by_name",
        user_message="We couldn't check that username right now. Please try again.",
    )
    if name_resp is None:
        return None
    return name_resp.data or []


def resolve_login_identifier(identifier: str):
    clean_identifier = identifier.strip()
    if not clean_identifier:
        return None, None, None, "identifier_empty"

    probe_candidates = [clean_identifier]
    normalized_candidate = _normalize_email(clean_identifier)
    if normalized_candidate not in probe_candidates:
        probe_candidates.append(normalized_candidate)

    for probe in probe_candidates:
        allowed_probe, registration_probe = get_email_status(probe)
        if allowed_probe is None and registration_probe is None:
            return None, None, None, "lookup_error"
        if allowed_probe or registration_probe:
            return probe, allowed_probe, registration_probe, None

    name_matches = get_registration_by_name(clean_identifier)
    if name_matches is None:
        return None, None, None, "lookup_error"
    if len(name_matches) > 1:
        return None, None, None, "multiple_name_matches"
    if len(name_matches) == 1:
        matched_email = str(name_matches[0].get("email") or "").strip()
        if not matched_email:
            return None, None, None, "name_without_email"
        matched_email = _normalize_email(matched_email)
        allowed_probe, registration_probe = get_email_status(matched_email)
        if allowed_probe is None and registration_probe is None:
            return None, None, None, "lookup_error"
        return matched_email, allowed_probe, registration_probe, None

    if _is_valid_email(normalized_candidate):
        return normalized_candidate, [], [], None

    return None, [], [], "username_not_found"


def get_attendee_names_for_session(session_id: int):
    bookings_resp = _execute_query(
        supabase.table("bookings_email")
        .select("email")
        .eq("session_id", session_id)
        .eq("status", "confirmed"),
        action="load_attendee_bookings",
        user_message="We couldn't load attendee names right now.",
        show_error=False,
    )
    if bookings_resp is None:
        return []

    bookings = bookings_resp.data or []

    if not bookings:
        return []

    emails = [b["email"] for b in bookings]

    regs_resp = _execute_query(
        supabase.table("registrations")
        .select("name, email")
        .in_("email", emails),
        action="load_attendee_registrations",
        user_message="We couldn't load attendee names right now.",
        show_error=False,
    )
    if regs_resp is None:
        return []

    regs = regs_resp.data or []

    email_to_name = {r["email"]: r["name"] for r in regs}
    names = [email_to_name.get(e, "Unknown") for e in emails]
    names.sort()

    return names


def cancel_booking_email(booking_id: int):
    return _execute_query(
        supabase.table("bookings_email")
        .update(
            {
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", booking_id)
        .eq("status", "confirmed"),  # important safety guard
        action="cancel_booking",
        user_message="Could not cancel this booking right now. Please try again.",
    )


def allow_email(email_addr: str, name: str):
    return _execute_query(
        supabase.table("allowed_emails").upsert(
            {"email": email_addr, "notes": f"Auto-approved ({name})"}
        ),
        action="allow_email",
        user_message="We couldn't enable booking for your email yet. Please try again.",
    )


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

def _wait_for_registration(email: str, timeout_s: float = 8.0, poll_interval_s: float = 0.5):
    deadline = time.time() + timeout_s
    last_allowed = []
    last_registration = []
    saw_status_error = False
    while time.time() < deadline:
        last_allowed, last_registration = get_email_status(email)
        if last_allowed is None and last_registration is None:
            saw_status_error = True
            time.sleep(poll_interval_s)
            continue
        if last_allowed or last_registration:
            return last_allowed, last_registration
        time.sleep(poll_interval_s)
    if saw_status_error and not last_allowed and not last_registration:
        return None, None
    return last_allowed, last_registration


email = _get_auth_email()
if not email:
    st.warning("Please sign in on Home first, then come back.")
    st.page_link("Home.py", label="Go to login")
    st.stop()

allowed, registration = get_email_status(email)
if allowed is None and registration is None:
    st.stop()

if registration and sync_team_affiliation(registration[0]):
    st.rerun()

if st.session_state.get("just_registered"):
    st.success("Thanks! You're approved and can book now.")
    st.session_state.pop("just_registered", None)

if not allowed and not registration:
    st.warning("You are not registered yet. Please register on Home first.")
    st.page_link("Home.py", label="Go to login/registration")
    st.stop()

# --------------------------------------------------
# STATUS GATE
# --------------------------------------------------
if allowed:
    welcome_name = registration[0]["name"] if registration else "member"
    if st.session_state.get("welcome_name") != welcome_name:
        _set_state_safe("welcome_name", welcome_name)
    if not st.session_state.get("logged_in"):
        if not _set_state_safe("logged_in", True):
            st.stop()
        st.rerun()

elif registration:
    status = registration[0]["status"]

    if status == "approved":
        welcome_name = registration[0]["name"] or "member"
        if st.session_state.get("welcome_name") != welcome_name:
            _set_state_safe("welcome_name", welcome_name)
        if not allowed and not st.session_state.get("allowed_sync_attempted"):
            st.session_state["allowed_sync_attempted"] = True
            resp = allow_email(email, registration[0]["name"])
            if resp is not None:
                _debug_action(
                    "allow_email",
                    [resp],
                    context=f"email={email}",
                )
                st.cache_data.clear()
                st.rerun()
            st.error("We couldn't enable booking for your email yet.")
            st.stop()
        if not st.session_state.get("logged_in"):
            if not _set_state_safe("logged_in", True):
                st.stop()
            st.rerun()

    status_notice = registration_status_message(status)
    if status_notice:
        notice_type, notice_message = status_notice
        if notice_type == "warning":
            st.warning(notice_message)
        else:
            st.error(notice_message)
        st.stop()

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
sessions_resp = _execute_query(
    supabase.table("session_availability")
    .select("*")
    .order("start_at"),
    action="load_sessions",
    user_message="We couldn't load sessions right now. Please refresh and try again.",
)
if sessions_resp is None:
    st.stop()
sessions = sessions_resp.data or []

if not sessions:
    st.warning("No sessions found.")
    st.stop()

# Get ALL bookings for this email
my_bookings_resp = _execute_query(
    supabase.table("bookings_email")
    .select("id, session_id")
    .eq("email", email)
    .eq("status", "confirmed"),
    action="load_my_bookings",
    user_message="We couldn't load your bookings right now. Please refresh and try again.",
)
if my_bookings_resp is None:
    st.stop()
my_bookings = my_bookings_resp.data or []

# Map session_id -> booking_id
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
        line = format_my_booking_line(s.get("notes"), fmt_start(s["start_at"]))
        if s.get("locked"):
            line = f"{line} _(locked)_"
        if is_past(start_dt):
            st.markdown(f"~~{line}~~")
        else:
            st.markdown(line)

st.divider()

# --------------------------------------------------
# UI
# --------------------------------------------------
st.subheader("Book Available Sessions")

open_sessions = [s for s in sessions if not s.get("locked")]

if not open_sessions:
    st.info("No sessions available to book right now.")

for i, s in enumerate(open_sessions):
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
                "Booked",
                disabled=True,
                key=f"booked_{session_id}",
            )
        else:
            if st.button(
                "Book",
                disabled=slots_remaining <= 0,
                key=f"book_{session_id}",
            ):
                resp = _execute_query(
                    supabase.rpc(
                        "book_session_email",
                        {
                            "p_session_id": session_id,
                            "p_email": email,
                        },
                    ),
                    action="book_session_email",
                    user_message="Booking failed. Please try again.",
                    custom_error_message=booking_failure_message,
                )
                if resp is not None:
                    _debug_action(
                        "book_session_email",
                        [resp],
                        context=f"session_id={session_id} email={email}",
                    )
                    st.cache_data.clear()
                    st.rerun()

    with col3:
        booking_id = my_bookings_by_session.get(session_id)

        if booking_id:
            if st.button("Cancel", key=f"cancel_{session_id}"):
                resp = cancel_booking_email(booking_id)
                if resp is None:
                    st.stop()
                _debug_action(
                    "cancel_booking_email",
                    [resp],
                    context=f"booking_id={booking_id} session_id={session_id} email={email}",
                )
                st.toast("Booking cancelled")
                st.cache_data.clear()
                st.rerun()

    attendees = get_attendee_names_for_session(session_id)
    my_name = registration[0]["name"] if registration else None

    with st.expander(f"Attendees ({len(attendees)})"):
        if not attendees:
            st.info("No one booked yet.")
        else:
            for n in attendees:
                if my_name and n == my_name:
                    st.markdown(f"- **{n} (You)**")
                else:
                    st.write(f"- {n}")
    if i < len(open_sessions) - 1:
        st.divider()

render_logout_footer("winter_nets")

