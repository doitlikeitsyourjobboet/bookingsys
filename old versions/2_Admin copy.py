import streamlit as st
from supabase import create_client
from datetime import datetime, timezone
from datetime import datetime, time

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
st.set_page_config(page_title="Admin – Nets Booking", layout="wide")

ADMIN_PASSWORD = "DILIYJ2026"

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

role = supabase.rpc("debug_current_role").execute().data
st.write("DB role:", role)

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

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def utc_now():
    return datetime.now(timezone.utc).isoformat()


def approve_registration(reg):
    supabase.table("allowed_emails").upsert(
        {"email": reg["email"], "notes": f"Approved ({reg['name']})"}
    ).execute()

    supabase.table("registrations").update(
        {"status": "approved", "reviewed_at": utc_now()}
    ).eq("id", reg["id"]).execute()


def reject_registration(reg):
    supabase.table("allowed_emails").delete().eq("email", reg["email"]).execute()

    supabase.table("registrations").update(
        {"status": "rejected", "reviewed_at": utc_now()}
    ).eq("id", reg["id"]).execute()


def delete_user_completely(reg):
    email = reg["email"]
    supabase.table("bookings_email").delete().eq("email", email).execute()
    supabase.table("allowed_emails").delete().eq("email", email).execute()
    supabase.table("registrations").delete().eq("id", reg["id"]).execute()


def remove_booking(booking_id):
    supabase.table("bookings_email").update(
        {"status": "cancelled", "cancelled_at": utc_now()}
    ).eq("id", booking_id).execute()


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
                    approve_registration(r)
                    refresh()
            with c3:
                if allow_reject and st.button("❌ Reject", key=f"r_{r['id']}"):
                    reject_registration(r)
                    refresh()
            with c4:
                if st.button("🗑️ Delete", key=f"d_{r['id']}"):
                    delete_user_completely(r)
                    refresh()

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
                    remove_booking(b["id"])
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

    with st.expander(f"{header} — {date_line} ({s['confirmed_count']}/{s['capacity']})"):    
        c1, c2, c3 = st.columns(3)

        with c1:
            start = st.datetime_input(
                "Start", value=datetime.fromisoformat(s["start_at"]), key=f"st_{s['id']}"
            )
            end = st.datetime_input(
                "End", value=datetime.fromisoformat(s["end_at"]), key=f"et_{s['id']}"
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

        if st.button("💾 Save", key=f"save_{s['id']}"):
            supabase.table("sessions").update(
                {
                    "start_at": start.isoformat(),
                    "end_at": end.isoformat(),
                    "capacity": cap,
                    "location": loc,
                    "notes": nts,
                }
            ).eq("id", s["id"]).execute()
            refresh()

        if st.button("🗑️ Delete session", key=f"del_{s['id']}"):
            supabase.table("sessions").delete().eq("id", s["id"]).execute()
            refresh()
