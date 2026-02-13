import streamlit as st
from supabase import create_client
from datetime import datetime, timezone, time
from app_nav import render_compact_nav, render_logout_footer

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Admin – Nets Booking",
    layout="wide",
    initial_sidebar_state="collapsed",
)
render_compact_nav("admin", include_admin=True)

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

def _get_secret(key: str, default=None):
    try:
        return st.secrets[key]
    except Exception:
        return default


ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_ANON_KEY = st.secrets["SUPABASE_ANON_KEY"]
SUPABASE_ADMIN_KEY = _get_secret("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_ANON_KEY)

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_ADMIN_KEY,
)

FIXTURE_TEAMS = {
    "plucky": "Plucky M's",
    "unabombers": "Unabombers",
}

if _secret_bool("DEBUG_MODE"):
    role = supabase.rpc("debug_current_role").execute().data
    st.caption(f"DB role: {role}")

# --------------------------------------------------
# FORMATTERS
# --------------------------------------------------
def fmt_date(dt: datetime) -> str:
    return dt.strftime("%d/%b/%Y").upper()

def fmt_time(dt: datetime) -> str:
    # Windows-safe: strip leading zero manually
    return dt.strftime("%I:%M%p").lstrip("0").lower()

def parse_iso(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)

def fmt_session_range(start: str, end: str) -> str:
    s = parse_iso(start)
    e = parse_iso(end)
    return f"{fmt_date(s)} · {fmt_time(s)} – {fmt_time(e)}"

# --------------------------------------------------
# PASSWORD GATE
# --------------------------------------------------
if "admin_authed" not in st.session_state:
    st.session_state.admin_authed = False

if not st.session_state.admin_authed:
    st.title("🔒 Admin Access")
    pwd = st.text_input("Enter admin password", type="password")

    if st.button("Unlock"):
        if pwd == ADMIN_PASSWORD:
            st.session_state.admin_authed = True
            st.success("Access granted")
            st.rerun()
        else:
            st.error("Incorrect password")

    st.stop()

# --------------------------------------------------
# HEADER
# --------------------------------------------------
st.title("🛠️ Admin – Nets Booking")
st.caption("Manage users, bookings, and sessions.")
DEBUG = False
DEBUG = _secret_bool("DEBUG_MODE")

if DEBUG and st.session_state.get("last_debug"):
    st.info("Last action debug")
    st.code(st.session_state.last_debug, language="text")

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def utc_now():
    return datetime.now(timezone.utc).isoformat()


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


def _execute_query(query, action: str, user_message: str):
    try:
        return query.execute()
    except Exception as exc:
        if DEBUG:
            st.session_state.last_debug = f"Action: {action}\n\nError:\n{exc}"
            st.error(f"{action} failed")
            st.code(str(exc))
        st.error(user_message)
        return None


def approve_registration(reg):
    resp1 = supabase.table("allowed_emails").upsert(
        {"email": reg["email"], "notes": f"Approved ({reg['name']})"}
    ).execute()

    resp2 = supabase.table("registrations").update(
        {"status": "approved", "reviewed_at": utc_now()}
    ).eq("id", reg["id"]).execute()
    return resp1, resp2


def reject_registration(reg):
    resp1 = supabase.table("allowed_emails").delete().eq("email", reg["email"]).execute()

    resp2 = supabase.table("registrations").update(
        {"status": "rejected", "reviewed_at": utc_now()}
    ).eq("id", reg["id"]).execute()
    return resp1, resp2


def delete_user_completely(reg):
    email = reg["email"]
    resp1 = supabase.table("bookings_email").delete().eq("email", email).execute()
    resp2 = supabase.table("allowed_emails").delete().eq("email", email).execute()
    resp3 = supabase.table("registrations").delete().eq("id", reg["id"]).execute()
    deleted = bool(resp3.data)
    return resp1, resp2, resp3, deleted


def remove_booking(booking_id):
    resp = supabase.table("bookings_email").update(
        {"status": "cancelled", "cancelled_at": utc_now()}
    ).eq("id", booking_id).execute()
    return resp


def remove_fixture_booking(booking_id):
    resp = supabase.table("fixture_bookings").update(
        {"status": "cancelled", "cancelled_at": utc_now()}
    ).eq("id", booking_id).execute()
    return resp


def fixture_title(fixture: dict) -> str:
    title = str(fixture.get("title") or "").strip()
    if title:
        return title
    team_key = str(fixture.get("team_key") or "").strip().lower()
    team_label = FIXTURE_TEAMS.get(team_key, team_key.title() or "Team")
    opponent = str(fixture.get("opponent") or "").strip()
    if opponent:
        return f"{team_label} vs {opponent}"
    notes = str(fixture.get("notes") or "").strip()
    if notes:
        return notes
    return f"{team_label} Fixture"


def refresh():
    st.cache_data.clear()
    st.rerun()

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------
registrations = (
    supabase.table("registrations")
    .select("*")
    .order("created_at")
    .execute()
    .data
) or []

pending = [r for r in registrations if r["status"] == "pending"]
approved = [r for r in registrations if r["status"] == "approved"]
rejected = [r for r in registrations if r["status"] == "rejected"]

# --------------------------------------------------
# REGISTRATIONS
# --------------------------------------------------
st.subheader("👤 Registrations")

def render_reg_section(title, rows, allow_approve, allow_reject):
    st.markdown(f"### {title}")
    if not rows:
        st.info("None")
        return

    for r in rows:
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([4, 1, 1, 1])
            with c1:
                st.write(f"**{r['name']}**")
                st.write(r["email"])
                st.caption(f"Registered: {r['created_at']}")
            with c2:
                if allow_approve and st.button("✅ Approve", key=f"a_{r['id']}"):
                    resp1, resp2 = approve_registration(r)
                    _debug_action(
                        "approve_registration",
                        [resp1, resp2],
                        context=f"id={r['id']} email={r['email']}",
                    )
                    refresh()
            with c3:
                if allow_reject and st.button("❌ Reject", key=f"r_{r['id']}"):
                    resp1, resp2 = reject_registration(r)
                    _debug_action(
                        "reject_registration",
                        [resp1, resp2],
                        context=f"id={r['id']} email={r['email']}",
                    )
                    refresh()
            with c4:
                if st.button("🗑️ Delete", key=f"d_{r['id']}"):
                    resp1, resp2, resp3, deleted = delete_user_completely(r)
                    _debug_action(
                        "delete_user_completely",
                        [resp1, resp2, resp3],
                        context=f"id={r['id']} email={r['email']}",
                    )
                    if deleted:
                        refresh()
                    else:
                        st.error(
                            "Delete failed. This usually means the admin client "
                            "does not have permission to delete registrations."
                        )

render_reg_section("🟡 Pending", pending, True, True)
render_reg_section("✅ Approved", approved, False, True)
render_reg_section("❌ Rejected", rejected, True, False)

# --------------------------------------------------
# BOOKINGS
# --------------------------------------------------
st.divider()
st.subheader("📋 Active Bookings")

bookings = (
    supabase.table("bookings_email")
    .select("id, email, session_id, created_at")
    .eq("status", "confirmed")
    .order("created_at")
    .execute()
    .data
) or []

if not bookings:
    st.info("No active bookings.")
else:
    for b in bookings:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                st.write(f"**{b['email']}**")
                st.caption(f"Session ID: {b['session_id']} | {b['created_at']}")
            with c2:
                if st.button("🧹 Remove", key=f"rb_{b['id']}"):
                    resp = remove_booking(b["id"])
                    _debug_action(
                        "remove_booking",
                        [resp],
                        context=f"id={b['id']} email={b['email']}",
                    )
                    refresh()

# --------------------------------------------------
# SESSIONS MANAGEMENT
# --------------------------------------------------
st.divider()
st.subheader("🗓️ Sessions")

# ---- CREATE SESSION ----
with st.expander("➕ Add new session"):
    today = datetime.now().date()

    default_start = datetime.combine(today, time(19, 35))
    default_end = datetime.combine(today, time(21, 0))

    c1, c2 = st.columns(2)

    with c1:
        start_at = st.datetime_input(
            "Start time",
            value=default_start,
            key="new_session_start",
        )
        capacity = st.number_input(
            "Capacity",
            min_value=1,
            value=24,
        )

    with c2:
        end_at = st.datetime_input(
            "End time",
            value=default_end,
            key="new_session_end",
        )
        location = st.text_input("Location")

    notes = st.text_input("Notes")

    if st.button("Create session"):
        if end_at <= start_at:
            st.warning("End time must be after start time.")
            st.stop()

        supabase.table("sessions").insert(
            {
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "capacity": capacity,
                "location": location,
                "notes": notes,
            }
        ).execute()

        st.cache_data.clear()
        st.success("Session created.")
        st.rerun()

# ---- EXISTING SESSIONS ----
sessions = (
    supabase.table("session_availability")
    .select("*")
    .order("start_at")
    .execute()
    .data
) or []

for s in sessions:

    header = s.get("notes") or "Training Session"
    date_line = fmt_session_range(s["start_at"], s["end_at"])
    locked = bool(s.get("locked"))
    lock_suffix = " [LOCKED]" if locked else ""

    with st.expander(f"{header} — {date_line} ({s['confirmed_count']}/{s['capacity']}){lock_suffix}"):    
        c1, c2, c3 = st.columns(3)

        with c1:
            start = st.datetime_input(
                "Start", value=parse_iso(s["start_at"]), key=f"st_{s['id']}"
            )
            end = st.datetime_input(
                "End", value=parse_iso(s["end_at"]), key=f"et_{s['id']}"
            )

        with c2:
            cap = st.number_input(
                "Capacity", min_value=1, value=s["capacity"], key=f"cap_{s['id']}"
            )
            loc = st.text_input(
                "Location", value=s.get("location") or "", key=f"loc_{s['id']}"
            )

        with c3:
            nts = st.text_input(
                "Notes", value=s.get("notes") or "", key=f"nts_{s['id']}"
            )
            locked_toggle = st.checkbox(
                "Locked",
                value=locked,
                key=f"locked_{s['id']}",
                help="When locked, players cannot book or cancel this session.",
            )

        if st.button("💾 Save", key=f"save_{s['id']}"):
            supabase.table("sessions").update(
                {
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "capacity": cap,
                    "location": loc,
                    "notes": nts,
                    "locked": locked_toggle,
                }
            ).eq("id", s["id"]).execute()
            refresh()

        if st.button("🗑️ Delete session", key=f"del_{s['id']}"):
            supabase.table("sessions").delete().eq("id", s["id"]).execute()
            refresh()

# --------------------------------------------------
# FIXTURE BOOKINGS
# --------------------------------------------------
st.divider()
st.subheader("Fixture Confirmations")

fixture_lookup_resp = _execute_query(
    supabase.table("fixture_availability")
    .select("id, team_key, title, opponent, notes, start_at, end_at")
    .order("start_at"),
    action="load_fixture_lookup",
    user_message=(
        "We couldn't load fixtures. "
        "Run supabase/fixtures_schema.sql if fixture tables are not created yet."
    ),
)
fixture_lookup_rows = fixture_lookup_resp.data if fixture_lookup_resp is not None else []
fixture_lookup = {row["id"]: row for row in fixture_lookup_rows}

fixture_bookings_resp = _execute_query(
    supabase.table("fixture_bookings")
    .select("id, email, fixture_id, created_at")
    .eq("status", "confirmed")
    .order("created_at"),
    action="load_fixture_bookings",
    user_message=(
        "We couldn't load fixture confirmations. "
        "Run supabase/fixtures_schema.sql if fixture tables are not created yet."
    ),
)
fixture_bookings = fixture_bookings_resp.data if fixture_bookings_resp is not None else []

if not fixture_bookings:
    st.info("No active fixture confirmations.")
else:
    for booking in fixture_bookings:
        with st.container(border=True):
            c1, c2 = st.columns([5, 1])
            with c1:
                fixture = fixture_lookup.get(booking["fixture_id"], {})
                if fixture:
                    label = fixture_title(fixture)
                    date_line = fmt_session_range(
                        fixture["start_at"],
                        fixture["end_at"],
                    )
                else:
                    label = f"Fixture ID {booking['fixture_id']}"
                    date_line = "Fixture details unavailable"
                st.write(f"**{booking['email']}**")
                st.caption(f"{label} | {date_line} | {booking['created_at']}")
            with c2:
                if st.button("Remove", key=f"rfb_{booking['id']}"):
                    resp = remove_fixture_booking(booking["id"])
                    _debug_action(
                        "remove_fixture_booking",
                        [resp],
                        context=f"id={booking['id']} email={booking['email']}",
                    )
                    refresh()

# --------------------------------------------------
# FIXTURE MANAGEMENT
# --------------------------------------------------
st.divider()
st.subheader("Fixtures")

with st.expander("Add new fixture"):
    today = datetime.now().date()
    default_start = datetime.combine(today, time(13, 0))
    default_end = datetime.combine(today, time(17, 0))

    c1, c2 = st.columns(2)

    with c1:
        new_team_key = st.selectbox(
            "Team",
            options=list(FIXTURE_TEAMS.keys()),
            format_func=lambda value: FIXTURE_TEAMS[value],
            key="new_fixture_team_key",
        )
        new_start_at = st.datetime_input(
            "Start time",
            value=default_start,
            key="new_fixture_start",
        )
        new_capacity = st.number_input(
            "Capacity",
            min_value=1,
            value=11,
            key="new_fixture_capacity",
        )

    with c2:
        new_opponent = st.text_input(
            "Opponent",
            key="new_fixture_opponent",
            placeholder="Example: Unabombers",
        )
        new_end_at = st.datetime_input(
            "End time",
            value=default_end,
            key="new_fixture_end",
        )
        new_location = st.text_input(
            "Location",
            key="new_fixture_location",
        )

    new_title = st.text_input(
        "Fixture title (optional)",
        key="new_fixture_title",
        placeholder="If empty, title falls back to '<Team> vs <Opponent>'.",
    )
    new_notes = st.text_input("Notes", key="new_fixture_notes")
    new_locked = st.checkbox(
        "Locked",
        value=False,
        key="new_fixture_locked",
        help="When locked, players cannot confirm or cancel this fixture.",
    )

    if st.button("Create fixture", key="create_fixture_button"):
        if new_end_at <= new_start_at:
            st.warning("End time must be after start time.")
        else:
            payload = {
                "team_key": new_team_key,
                "title": new_title.strip() or None,
                "opponent": new_opponent.strip() or None,
                "start_at": new_start_at.isoformat(),
                "end_at": new_end_at.isoformat(),
                "capacity": int(new_capacity),
                "location": new_location.strip() or None,
                "notes": new_notes.strip() or None,
                "locked": new_locked,
            }
            response = _execute_query(
                supabase.table("fixtures").insert(payload),
                action="create_fixture",
                user_message=(
                    "Could not create fixture. "
                    "Run supabase/fixtures_schema.sql if fixture tables are missing."
                ),
            )
            if response is not None:
                _debug_action("create_fixture", [response], context=str(payload))
                refresh()

fixtures_resp = _execute_query(
    supabase.table("fixture_availability")
    .select("*")
    .order("start_at"),
    action="load_fixture_availability",
    user_message=(
        "Could not load fixtures. "
        "Run supabase/fixtures_schema.sql if fixture tables are missing."
    ),
)
fixtures = fixtures_resp.data if fixtures_resp is not None else []

if not fixtures:
    st.info("No fixtures found.")
else:
    team_keys = list(FIXTURE_TEAMS.keys())
    for fixture in fixtures:
        header = fixture_title(fixture)
        date_line = fmt_session_range(fixture["start_at"], fixture["end_at"])
        locked = bool(fixture.get("locked"))
        lock_suffix = " [LOCKED]" if locked else ""
        team_key = str(fixture.get("team_key") or "plucky").lower()
        team_label = FIXTURE_TEAMS.get(team_key, team_key.title())

        with st.expander(
            (
                f"{team_label}: {header} - {date_line} "
                f"({fixture['confirmed_count']}/{fixture['capacity']}){lock_suffix}"
            )
        ):
            c1, c2, c3 = st.columns(3)

            with c1:
                start_at = st.datetime_input(
                    "Start",
                    value=parse_iso(fixture["start_at"]),
                    key=f"fst_{fixture['id']}",
                )
                end_at = st.datetime_input(
                    "End",
                    value=parse_iso(fixture["end_at"]),
                    key=f"fet_{fixture['id']}",
                )
                capacity = st.number_input(
                    "Capacity",
                    min_value=1,
                    value=int(fixture["capacity"]),
                    key=f"fcap_{fixture['id']}",
                )

            with c2:
                team_value = st.selectbox(
                    "Team",
                    options=team_keys,
                    index=team_keys.index(team_key) if team_key in team_keys else 0,
                    format_func=lambda value: FIXTURE_TEAMS[value],
                    key=f"fteam_{fixture['id']}",
                )
                opponent = st.text_input(
                    "Opponent",
                    value=str(fixture.get("opponent") or ""),
                    key=f"fopp_{fixture['id']}",
                )
                location = st.text_input(
                    "Location",
                    value=str(fixture.get("location") or ""),
                    key=f"floc_{fixture['id']}",
                )

            with c3:
                title = st.text_input(
                    "Title",
                    value=str(fixture.get("title") or ""),
                    key=f"ftitle_{fixture['id']}",
                )
                notes = st.text_input(
                    "Notes",
                    value=str(fixture.get("notes") or ""),
                    key=f"fnotes_{fixture['id']}",
                )
                locked_toggle = st.checkbox(
                    "Locked",
                    value=locked,
                    key=f"flocked_{fixture['id']}",
                )

            if st.button("Save fixture", key=f"save_fixture_{fixture['id']}"):
                if end_at <= start_at:
                    st.warning("End time must be after start time.")
                else:
                    payload = {
                        "team_key": team_value,
                        "title": title.strip() or None,
                        "opponent": opponent.strip() or None,
                        "start_at": start_at.isoformat(),
                        "end_at": end_at.isoformat(),
                        "capacity": int(capacity),
                        "location": location.strip() or None,
                        "notes": notes.strip() or None,
                        "locked": locked_toggle,
                    }
                    response = _execute_query(
                        supabase.table("fixtures")
                        .update(payload)
                        .eq("id", fixture["id"]),
                        action="update_fixture",
                        user_message="Could not update fixture.",
                    )
                    if response is not None:
                        _debug_action(
                            "update_fixture",
                            [response],
                            context=f"id={fixture['id']} payload={payload}",
                        )
                        refresh()

            if st.button("Delete fixture", key=f"del_fixture_{fixture['id']}"):
                response = _execute_query(
                    supabase.table("fixtures").delete().eq("id", fixture["id"]),
                    action="delete_fixture",
                    user_message="Could not delete fixture.",
                )
                if response is not None:
                    _debug_action(
                        "delete_fixture",
                        [response],
                        context=f"id={fixture['id']}",
                    )
                    refresh()

render_logout_footer("admin")
