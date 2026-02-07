##we are now public v2.6

import streamlit as st
import base64
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

def _img_to_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"

logo_pluckys = _img_to_data_uri("visuals/pluckys.png")
logo_bombers = _img_to_data_uri("visuals/bombers.png")

st.markdown(
    f"""
<style>
.logo-row {{
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: nowrap;
}}
.logo-row img {{
  width: 100px;
  height: auto;
}}
</style>
<div class="logo-row">
  <img src="{logo_pluckys}" alt="Pluckys logo">
  <img src="{logo_bombers}" alt="Bombers logo">
</div>
""",
    unsafe_allow_html=True,
)

st.subheader("Kings Winter Nets")
st.text("Winter cricket nets are open for booking.")
st.caption("Book your spot for our winter net sessions!")

DEBUG = False
if _secret_bool("DEBUG_MODE"):
    DEBUG = st.sidebar.checkbox("Debug mode", value=False)

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
        .select("id, name, status")
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


# --------------------------------------------------
# EMAIL ENTRY
# --------------------------------------------------
if _get_auth_email():
    email = _get_auth_email()
else:
    with st.form("email_lookup_form", clear_on_submit=False):
        email_input = st.text_input(
            "Your username / email address",
            placeholder="you@example.com",
            key=AUTH_EMAIL_INPUT_KEY,
        )
        submit_email = st.form_submit_button("Continue", use_container_width=True)

    decision = evaluate_email_form(submit_email, email_input)
    if decision.should_stop:
        if decision.message_type == "info":
            st.info(decision.message)
        else:
            st.warning(decision.message)
        st.stop()

    login_identifier = decision.email or ""
    email, _, _, resolve_error = resolve_login_identifier(login_identifier)
    if resolve_error == "lookup_error":
        st.stop()
    if resolve_error == "multiple_name_matches":
        st.error("Multiple users share that full name. Please log in with your email.")
        st.stop()
    if resolve_error == "name_without_email":
        st.error("This username has no linked email. Please contact an admin.")
        st.stop()
    if resolve_error == "username_not_found":
        st.warning("Username not found. If you are new, enter your email to register.")
        st.stop()
    if not email:
        st.warning(EMAIL_REQUIRED_MESSAGE)
        st.stop()

    if not _set_state_safe(AUTH_EMAIL_KEY, email):
        st.stop()
    if decision.should_rerun:
        st.rerun()

if not email:
    st.info(EMAIL_REQUIRED_MESSAGE)
    st.stop()

allowed, registration = get_email_status(email)
if allowed is None and registration is None:
    st.stop()

if st.session_state.get("just_registered"):
    st.success("Thanks! You're approved and can book now.")
    st.session_state.pop("just_registered", None)

# --------------------------------------------------
# INLINE REGISTRATION
# --------------------------------------------------
if not allowed and not registration:
    st.subheader("First time here? Register")

    name = st.text_input("Full name")

    if st.button("Register"):
        if not _is_valid_email(email):
            st.warning("Please enter a valid email address before registering.")
            st.stop()

        clean_name = name.strip()
        if not clean_name:
            st.warning("Please enter your full name.")
            st.stop()

        with st.spinner("Registering and logging you in..."):
            resp_reg = _execute_query(
                supabase.table("registrations").insert(
                    {
                        "name": clean_name,
                        "email": email,
                        "status": "approved",
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                action="register_user",
                user_message="Registration failed. Please try again.",
            )
            if resp_reg is None:
                st.stop()

            resp_allow = allow_email(email, clean_name)
            if resp_allow is None:
                st.stop()

            allowed, registration = _wait_for_registration(email)
            if allowed is None and registration is None:
                st.warning(
                    "Registration saved, but we couldn't verify it yet. "
                    "Please refresh and try again shortly."
                )
                st.stop()
            if not allowed and not registration:
                st.warning(
                    "Registration saved, but we couldn't verify it yet. "
                    "Please try again in a few seconds."
                )
                st.stop()

        _debug_action(
            "register_and_allow",
            [resp_reg, resp_allow],
            context=f"email={email}",
        )

        st.cache_data.clear()
        ok = all(
            [
                _set_state_safe(
                    AUTH_EMAIL_KEY,
                    email,
                    user_message="Registration worked, but we couldn't persist your session email.",
                ),
                _set_state_safe(
                    "logged_in",
                    True,
                    user_message="Registration worked, but we couldn't complete sign-in. Please try again.",
                ),
                _set_state_safe("just_registered", True),
            ]
        )
        if not ok:
            st.stop()
        st.rerun()

    st.stop()

# --------------------------------------------------
# STATUS GATE
# --------------------------------------------------
if allowed:
    if not st.session_state.get("logged_in"):
        if not _set_state_safe("logged_in", True):
            st.stop()
        st.rerun()
    welcome_name = registration[0]["name"] if registration else "member"
    st.success(f"Welcome, {welcome_name}")
    if st.button("Log out"):
        if not _set_state_safe("do_logout", True):
            st.stop()
        st.rerun()

elif registration:
    status = registration[0]["status"]

    if status == "approved":
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
        st.success(f"Welcome, {registration[0]['name']}")
        if st.button("Log out"):
            if not _set_state_safe("do_logout", True):
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
    if i < len(sessions) - 1:
        st.divider()


