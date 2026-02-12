from datetime import datetime, timezone

import streamlit as st
from streamlit.errors import StreamlitAPIException
from supabase import create_client

from app_nav import render_compact_nav
from booking_rules import (
    AUTH_EMAIL_INPUT_KEY,
    AUTH_EMAIL_KEY,
    booking_failure_message,
    format_my_booking_line,
    normalize_email,
    registration_status_message,
)


REQUIRED_SECRETS = ["SUPABASE_URL", "SUPABASE_ANON_KEY"]
TEAM_LABELS = {
    "plucky": "Plucky",
    "unabombers": "Unabombers",
}
FIXTURE_SCHEMA_HINT = (
    "Fixture tables are not set up yet. Ask an admin to run "
    "`supabase/fixtures_schema.sql` in Supabase SQL Editor, then refresh."
)


def _has_secret(key: str) -> bool:
    return key in st.secrets


def _secret_bool(key: str, default: bool = False) -> bool:
    try:
        value = st.secrets[key]
    except Exception:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_iso(timestamp: str) -> datetime:
    if timestamp.endswith("Z"):
        timestamp = timestamp[:-1] + "+00:00"
    return datetime.fromisoformat(timestamp)


def _day_suffix(day: int) -> str:
    if 11 <= day % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def _fmt_date(value: datetime) -> str:
    return f"{value.day}{_day_suffix(value.day)} {value.strftime('%b %Y')}"


def _fmt_time(value: datetime) -> str:
    return value.strftime("%I:%M%p").lstrip("0").lower()


def _fmt_start(start_at: str) -> str:
    timestamp = _parse_iso(start_at)
    return f"{_fmt_date(timestamp)} @{_fmt_time(timestamp)}"


def _is_past(value: datetime) -> bool:
    if value.tzinfo is None:
        return value < datetime.now()
    return value < datetime.now(timezone.utc)


def _team_label(team_key: str) -> str:
    return TEAM_LABELS.get(team_key, team_key.title())


def _fixture_name(fixture: dict, team_key: str, default_label: str) -> str:
    title = str(fixture.get("title") or "").strip()
    if title:
        return title

    opponent = str(fixture.get("opponent") or "").strip()
    if opponent:
        return f"{_team_label(team_key)} vs {opponent}"

    notes = str(fixture.get("notes") or "").strip()
    if notes:
        return notes

    return default_label


def _is_fixture_schema_error(error: Exception | str) -> bool:
    text = str(error).lower()
    fixture_markers = (
        "fixture_availability",
        "fixture_bookings",
        "fixtures",
        "book_fixture_email",
    )
    schema_markers = (
        "does not exist",
        "could not find the table",
        "could not find the function",
        "relation",
        "schema cache",
    )
    return any(marker in text for marker in fixture_markers) and any(
        marker in text for marker in schema_markers
    )


def _fixture_booking_failure_message(error: Exception | str) -> str:
    text = str(error).lower()
    if "already_booked" in text or "duplicate key" in text:
        return "You have already confirmed this fixture."
    if "fixture_full" in text:
        return "This fixture is full."
    if "fixture_locked" in text:
        return "This fixture is locked right now."
    if "fixture_not_found" in text:
        return "That fixture is no longer available."
    return booking_failure_message(error)


def render_fixture_page(
    *,
    team_key: str,
    heading: str,
    description: str,
    caption: str,
    empty_message: str,
    default_fixture_label: str,
) -> None:
    missing = [key for key in REQUIRED_SECRETS if not _has_secret(key)]
    if missing:
        st.error("Missing required configuration.")
        st.code("\n".join(missing))
        st.info(
            "For local dev: add them to `.streamlit/secrets.toml`\n"
            "For Streamlit Cloud: App -> Settings -> Secrets"
        )
        st.stop()

    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_ANON_KEY"],
    )

    debug = False
    if _secret_bool("DEBUG_MODE"):
        debug = st.sidebar.checkbox(
            "Debug mode",
            value=False,
            key=f"{team_key}_debug_mode",
        )

    if debug and st.session_state.get("last_debug"):
        st.info("Last action debug")
        st.code(st.session_state.last_debug, language="text")

    def _set_state_safe(
        key: str,
        value,
        user_message: str | None = None,
    ) -> bool:
        try:
            st.session_state[key] = value
            return True
        except StreamlitAPIException as exc:
            if debug:
                st.error(f"Session state update failed for key: {key}")
                st.code(str(exc))
            st.warning(
                user_message
                or "We hit a temporary session issue. Please refresh and try again."
            )
            return False

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
            if debug:
                st.session_state.last_debug = f"Action: {action}\n\nError:\n{exc}"
                st.error(f"{action} failed")
                st.code(str(exc))
            if show_error:
                if callable(custom_error_message):
                    st.error(custom_error_message(exc))
                else:
                    st.error(user_message)
            return None

    def _resp_summary(resp) -> str:
        parts = []
        for attr in ("status_code", "status", "error", "count"):
            if hasattr(resp, attr):
                parts.append(f"{attr}={getattr(resp, attr)}")
        data = getattr(resp, "data", None)
        if data is not None:
            parts.append(f"data={data}")
        return "\n".join(parts) if parts else repr(resp)

    def _debug_action(action: str, responses, context: str = "") -> None:
        if not debug:
            return
        lines = [f"Action: {action}"]
        if context:
            lines.append(f"Context: {context}")
        for i, resp in enumerate(responses, 1):
            lines.append(f"\nResponse {i}:\n{_resp_summary(resp)}")
        st.session_state.last_debug = "\n".join(lines)

    def _get_auth_email() -> str:
        value = st.session_state.get(AUTH_EMAIL_KEY)
        if isinstance(value, str):
            return normalize_email(value)
        return ""

    def _fixture_schema_message(default_message: str):
        def _inner(error: Exception | str) -> str:
            if _is_fixture_schema_error(error):
                return FIXTURE_SCHEMA_HINT
            return default_message

        return _inner

    def _get_email_status(email: str):
        allowed_resp = _execute_query(
            supabase.table("allowed_emails").select("email").eq("email", email),
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
            user_message=(
                "We couldn't check your registration status right now. "
                "Please try again."
            ),
        )
        if registration_resp is None:
            return None, None

        return (allowed_resp.data or []), (registration_resp.data or [])

    def _allow_email(email_addr: str, name: str):
        return _execute_query(
            supabase.table("allowed_emails").upsert(
                {"email": email_addr, "notes": f"Auto-approved ({name})"}
            ),
            action="allow_email",
            user_message=(
                "We couldn't enable fixture booking for your email yet. "
                "Please try again."
            ),
        )

    def _cancel_fixture_booking(booking_id: int):
        return _execute_query(
            supabase.table("fixture_bookings")
            .update(
                {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", booking_id)
            .eq("status", "confirmed"),
            action="cancel_fixture_booking",
            user_message=(
                "Could not cancel this fixture confirmation right now. "
                "Please try again."
            ),
            custom_error_message=_fixture_schema_message(
                "Could not cancel this fixture confirmation right now. Please try again."
            ),
        )

    def _get_attendee_names_for_fixture(fixture_id: int) -> list[str]:
        booking_resp = _execute_query(
            supabase.table("fixture_bookings")
            .select("email")
            .eq("fixture_id", fixture_id)
            .eq("status", "confirmed"),
            action="load_fixture_attendee_bookings",
            user_message="We couldn't load attendee names right now.",
            show_error=False,
        )
        if booking_resp is None:
            return []

        bookings = booking_resp.data or []
        if not bookings:
            return []

        emails = [row["email"] for row in bookings]
        registrations_resp = _execute_query(
            supabase.table("registrations")
            .select("name, email")
            .in_("email", emails),
            action="load_fixture_attendee_registrations",
            user_message="We couldn't load attendee names right now.",
            show_error=False,
        )
        if registrations_resp is None:
            return []

        registrations = registrations_resp.data or []
        email_to_name = {row["email"]: row["name"] for row in registrations}
        names = [email_to_name.get(email, "Unknown") for email in emails]
        names.sort()
        return names

    def _execute_without_ui(query):
        try:
            return query.execute(), None
        except Exception as exc:
            return None, exc

    def _book_fixture(fixture_id: int, email: str):
        rpc_response, rpc_error = _execute_without_ui(
            supabase.rpc(
                "book_fixture_email",
                {
                    "p_fixture_id": fixture_id,
                    "p_email": email,
                },
            )
        )
        if rpc_response is not None:
            return rpc_response

        rpc_error_text = str(rpc_error).lower() if rpc_error else ""
        missing_rpc = "book_fixture_email" in rpc_error_text and (
            "could not find the function" in rpc_error_text
            or "does not exist" in rpc_error_text
        )
        if missing_rpc:
            return _execute_query(
                supabase.table("fixture_bookings").insert(
                    {
                        "fixture_id": fixture_id,
                        "email": email,
                        "status": "confirmed",
                    }
                ),
                action="book_fixture_insert",
                user_message="Fixture confirmation failed. Please try again.",
                custom_error_message=_fixture_booking_failure_message,
            )

        if rpc_error is not None:
            if debug:
                st.session_state.last_debug = f"Action: book_fixture_email\n\nError:\n{rpc_error}"
            if _is_fixture_schema_error(rpc_error):
                st.error(FIXTURE_SCHEMA_HINT)
            else:
                st.error(_fixture_booking_failure_message(rpc_error))
        return None

    if st.session_state.get("do_logout"):
        _set_state_safe(AUTH_EMAIL_KEY, "")
        _set_state_safe(AUTH_EMAIL_INPUT_KEY, "")
        st.session_state.pop("logged_in", None)
        st.session_state.pop("last_debug", None)
        st.session_state.pop("allowed_sync_attempted", None)
        st.session_state.pop("just_registered", None)
        st.session_state.pop("welcome_name", None)
        st.session_state.pop("do_logout", None)

    current_page = {
        "plucky": "plucky_fixtures",
        "unabombers": "unabombers_fixtures",
    }.get(team_key, "")
    render_compact_nav(current_page)

    st.subheader(heading)
    st.text(description)
    st.caption(caption)

    email = _get_auth_email()
    if not email:
        st.warning("Please sign in on Home first, then come back.")
        st.page_link("Home.py", label="Go to login")
        st.stop()

    allowed, registration = _get_email_status(email)
    if allowed is None and registration is None:
        st.stop()

    if st.session_state.get("just_registered"):
        st.success("Thanks! You're approved and can book now.")
        st.session_state.pop("just_registered", None)

    if not allowed and not registration:
        st.warning("You are not registered yet. Please register on Home first.")
        st.page_link("Home.py", label="Go to login/registration")
        st.stop()

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
                response = _allow_email(email, registration[0]["name"])
                if response is not None:
                    _debug_action(
                        "allow_email",
                        [response],
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

    fixtures_resp = _execute_query(
        supabase.table("fixture_availability")
        .select("*")
        .eq("team_key", team_key)
        .order("start_at"),
        action="load_fixture_availability",
        user_message="We couldn't load fixtures right now. Please refresh and try again.",
        custom_error_message=_fixture_schema_message(
            "We couldn't load fixtures right now. Please refresh and try again."
        ),
    )
    if fixtures_resp is None:
        st.stop()
    fixtures = fixtures_resp.data or []

    my_bookings_resp = _execute_query(
        supabase.table("fixture_bookings")
        .select("id, fixture_id")
        .eq("email", email)
        .eq("status", "confirmed"),
        action="load_my_fixture_bookings",
        user_message=(
            "We couldn't load your fixture confirmations right now. "
            "Please refresh and try again."
        ),
        custom_error_message=_fixture_schema_message(
            "We couldn't load your fixture confirmations right now. Please refresh and try again."
        ),
    )
    if my_bookings_resp is None:
        st.stop()
    my_bookings = my_bookings_resp.data or []
    my_bookings_by_fixture = {row["fixture_id"]: row["id"] for row in my_bookings}

    st.subheader("My Fixture Availability")
    if not my_bookings:
        st.info("No fixture confirmations yet.")
    else:
        booked_rows = []
        for booking in my_bookings:
            fixture = next(
                (item for item in fixtures if item["id"] == booking["fixture_id"]),
                None,
            )
            if fixture:
                booked_rows.append((_parse_iso(fixture["start_at"]), fixture))

        if not booked_rows:
            st.info("No visible fixture confirmations on this team page.")
        else:
            for start_dt, fixture in sorted(booked_rows, key=lambda row: row[0]):
                fixture_title = _fixture_name(fixture, team_key, default_fixture_label)
                line = format_my_booking_line(fixture_title, _fmt_start(fixture["start_at"]))
                if fixture.get("locked"):
                    line = f"{line} _(locked)_"
                if _is_past(start_dt):
                    st.markdown(f"~~{line}~~")
                else:
                    st.markdown(line)

    st.divider()
    st.subheader("Confirm Availability")

    if not fixtures:
        st.info(empty_message)
        st.stop()

    open_fixtures = [fixture for fixture in fixtures if not fixture.get("locked")]
    if not open_fixtures:
        st.info("No fixtures are open for availability right now.")
        st.stop()

    my_name = registration[0]["name"] if registration else None

    for index, fixture in enumerate(open_fixtures):
        fixture_id = fixture["id"]
        slots_remaining = int(fixture.get("slots_remaining") or 0)
        capacity = int(fixture.get("capacity") or 0)

        col1, col2, col3, _ = st.columns([1.3, 0.5, 0.5, 3])

        with col1:
            fixture_title = _fixture_name(fixture, team_key, default_fixture_label)
            st.markdown(f"##### {fixture_title}")

            opponent = str(fixture.get("opponent") or "").strip()
            if opponent:
                st.caption(f"Opponent: {opponent}")

            location = str(fixture.get("location") or "").strip()
            start_line = _fmt_start(fixture["start_at"])
            line = f"{start_line} - {location}" if location else start_line
            st.markdown(f"###### {line}")
            st.caption(f"Spots: **{slots_remaining} / {capacity}**")

        with col2:
            if fixture_id in my_bookings_by_fixture:
                st.button(
                    "Confirmed",
                    disabled=True,
                    key=f"{team_key}_confirmed_{fixture_id}",
                )
            else:
                if st.button(
                    "Confirm",
                    disabled=slots_remaining <= 0,
                    key=f"{team_key}_book_{fixture_id}",
                ):
                    response = _book_fixture(fixture_id, email)
                    if response is not None:
                        _debug_action(
                            "book_fixture",
                            [response],
                            context=f"fixture_id={fixture_id} email={email}",
                        )
                        st.cache_data.clear()
                        st.rerun()

        with col3:
            booking_id = my_bookings_by_fixture.get(fixture_id)
            if booking_id and st.button("Cancel", key=f"{team_key}_cancel_{fixture_id}"):
                response = _cancel_fixture_booking(booking_id)
                if response is None:
                    st.stop()
                _debug_action(
                    "cancel_fixture_booking",
                    [response],
                    context=f"booking_id={booking_id} fixture_id={fixture_id} email={email}",
                )
                st.toast("Fixture confirmation cancelled")
                st.cache_data.clear()
                st.rerun()

        attendees = _get_attendee_names_for_fixture(fixture_id)
        with st.expander(f"Attendees ({len(attendees)})"):
            if not attendees:
                st.info("No one confirmed yet.")
            else:
                for attendee in attendees:
                    if my_name and attendee == my_name:
                        st.markdown(f"- **{attendee} (You)**")
                    else:
                        st.write(f"- {attendee}")

        if index < len(open_fixtures) - 1:
            st.divider()
