import base64

import streamlit as st
from supabase import create_client

from app_nav import render_compact_nav
from booking_rules import AUTH_EMAIL_KEY, normalize_email


st.set_page_config(page_title="My Profile", layout="wide")
render_compact_nav("profile")


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

DEBUG = False
if _secret_bool("DEBUG_MODE"):
    DEBUG = st.sidebar.checkbox("Debug mode", value=False)

PROFILE_PREFERENCE_OPTIONS = {
    "bowling": "Bowling",
    "batting": "Batting",
    "both": "Both",
}
PROFILE_PREFERENCE_VALUES = tuple(PROFILE_PREFERENCE_OPTIONS.keys())
PROFILE_PREFERENCE_FIELD_CANDIDATES = (
    "preference",
    "playing_preference",
    "player_preference",
)
PROFILE_BATTING_PREFERENCE_OPTIONS = {
    "not_set": "Not set",
    "orthodox": "Orthodox",
    "slogger": "Slogger",
}
PROFILE_BATTING_PREFERENCE_VALUES = tuple(PROFILE_BATTING_PREFERENCE_OPTIONS.keys())
PROFILE_BATTING_PREFERENCE_FIELD_CANDIDATES = (
    "batting_preference",
    "batting_style",
)
PROFILE_BATTING_PREFERENCE_ALIASES = {
    "authox": "orthodox",
    "orthodx": "orthodox",
}
PROFILE_BOWLING_PREFERENCE_OPTIONS = {
    "not_set": "Not set",
    "fast": "Fast",
    "slow": "Slow",
    "right_arm": "Right Arm",
    "left_arm": "Left Arm",
    "off_spin": "Off Spin",
    "leg_spin": "Leg Spin",
}
PROFILE_BOWLING_PREFERENCE_VALUES = tuple(PROFILE_BOWLING_PREFERENCE_OPTIONS.keys())
PROFILE_BOWLING_PREFERENCE_FIELD_CANDIDATES = (
    "bowling_preference",
    "bowling_style",
)
PROFILE_BOWLING_PREFERENCE_ALIASES = {
    "right-arm": "right_arm",
    "rightarm": "right_arm",
    "left-arm": "left_arm",
    "leftarm": "left_arm",
    "offspin": "off_spin",
    "legspin": "leg_spin",
}
PROFILE_BIO_FIELD_CANDIDATES = (
    "bio",
    "about_me",
)
PROFILE_IMAGE_FIELD_CANDIDATES = (
    "profile_photo_data",
    "profile_image_data",
    "avatar_data",
)
MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024


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


def _first_existing_field(record: dict, candidates: tuple[str, ...]) -> str | None:
    for field in candidates:
        if field in record:
            return field
    return None


def _normalize_profile_choice(
    value: str | None,
    allowed_values: tuple[str, ...],
    *,
    default: str,
    aliases: dict[str, str] | None = None,
) -> str:
    clean_value = str(value or "").strip().lower()
    if aliases and clean_value in aliases:
        clean_value = aliases[clean_value]
    clean_value = clean_value.replace(" ", "_")
    if clean_value in allowed_values:
        return clean_value
    return default


def _normalize_profile_preference(value: str | None) -> str:
    return _normalize_profile_choice(
        value,
        PROFILE_PREFERENCE_VALUES,
        default="both",
    )


def _profile_image_to_data_uri(uploaded_file) -> str:
    payload = base64.b64encode(uploaded_file.getvalue()).decode("ascii")
    mime = uploaded_file.type or "image/png"
    return f"data:{mime};base64,{payload}"


def _decode_profile_image(value: str | None):
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    encoded = raw
    if raw.startswith("data:") and "," in raw:
        encoded = raw.split(",", 1)[1]
    try:
        return base64.b64decode(encoded, validate=True)
    except Exception:
        try:
            return base64.b64decode(encoded)
        except Exception:
            return None


def _get_auth_email() -> str:
    value = st.session_state.get(AUTH_EMAIL_KEY)
    if isinstance(value, str):
        return normalize_email(value)
    return ""


st.title("My Profile")
st.caption(
    "Update your name, playing preference, batting and bowling styles, and profile photo."
)

email = _get_auth_email()
if not email:
    st.warning("Please sign in on Home first, then open this page.")
    st.stop()

st.caption(f"Signed in as: {email}")

registration_resp = _execute_query(
    supabase.table("registrations")
    .select("*")
    .eq("email", email)
    .order("created_at")
    .limit(1),
    action="load_profile",
    user_message="We couldn't load your profile right now. Please try again.",
)
if registration_resp is None:
    st.stop()

rows = registration_resp.data or []
if not rows:
    st.info("No registration record found for this email yet.")
    st.stop()

profile_record = rows[0]
profile_name_for_header = str(profile_record.get("name") or "").strip()
if profile_name_for_header and st.session_state.get("welcome_name") != profile_name_for_header:
    st.session_state["welcome_name"] = profile_name_for_header

preference_field = _first_existing_field(
    profile_record, PROFILE_PREFERENCE_FIELD_CANDIDATES
)
batting_preference_field = _first_existing_field(
    profile_record, PROFILE_BATTING_PREFERENCE_FIELD_CANDIDATES
)
bowling_preference_field = _first_existing_field(
    profile_record, PROFILE_BOWLING_PREFERENCE_FIELD_CANDIDATES
)
bio_field = _first_existing_field(profile_record, PROFILE_BIO_FIELD_CANDIDATES)
image_field = _first_existing_field(profile_record, PROFILE_IMAGE_FIELD_CANDIDATES)

saved_preference = _normalize_profile_preference(
    profile_record.get(preference_field) if preference_field else None
)
saved_preference_index = PROFILE_PREFERENCE_VALUES.index(saved_preference)
saved_batting_preference = _normalize_profile_choice(
    profile_record.get(batting_preference_field) if batting_preference_field else None,
    PROFILE_BATTING_PREFERENCE_VALUES,
    default="not_set",
    aliases=PROFILE_BATTING_PREFERENCE_ALIASES,
)
saved_batting_preference_index = PROFILE_BATTING_PREFERENCE_VALUES.index(
    saved_batting_preference
)
saved_bowling_preference = _normalize_profile_choice(
    profile_record.get(bowling_preference_field) if bowling_preference_field else None,
    PROFILE_BOWLING_PREFERENCE_VALUES,
    default="not_set",
    aliases=PROFILE_BOWLING_PREFERENCE_ALIASES,
)
saved_bowling_preference_index = PROFILE_BOWLING_PREFERENCE_VALUES.index(
    saved_bowling_preference
)
current_photo = _decode_profile_image(
    profile_record.get(image_field) if image_field else None
)

image_col, form_col = st.columns([1, 2])
with image_col:
    st.caption("Profile photo")
    if current_photo:
        st.image(current_photo, width=180)
    else:
        st.info("No photo uploaded.")

with form_col:
    with st.form("profile_form", clear_on_submit=False):
        profile_name = st.text_input(
            "Full name",
            value=str(profile_record.get("name") or ""),
            key="profile_name_input",
        )
        profile_preference = st.selectbox(
            "Preference",
            options=list(PROFILE_PREFERENCE_VALUES),
            index=saved_preference_index,
            format_func=lambda value: PROFILE_PREFERENCE_OPTIONS[value],
            key="profile_preference_input",
            disabled=preference_field is None,
        )
        batting_preference = st.selectbox(
            "Batting style",
            options=list(PROFILE_BATTING_PREFERENCE_VALUES),
            index=saved_batting_preference_index,
            format_func=lambda value: PROFILE_BATTING_PREFERENCE_OPTIONS[value],
            key="profile_batting_preference_input",
            disabled=batting_preference_field is None,
        )
        bowling_preference = st.selectbox(
            "Bowling style",
            options=list(PROFILE_BOWLING_PREFERENCE_VALUES),
            index=saved_bowling_preference_index,
            format_func=lambda value: PROFILE_BOWLING_PREFERENCE_OPTIONS[value],
            key="profile_bowling_preference_input",
            disabled=bowling_preference_field is None,
        )
        profile_bio = st.text_area(
            "About you (optional)",
            value=str(profile_record.get(bio_field) or "") if bio_field else "",
            key="profile_bio_input",
            max_chars=280,
            placeholder="Share a short note about your role or goals.",
            disabled=bio_field is None,
        )
        uploaded_photo = st.file_uploader(
            "Upload profile photo",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=False,
            key="profile_photo_uploader",
            disabled=image_field is None,
            help="Maximum file size: 2MB.",
        )
        remove_photo = st.checkbox(
            "Remove current profile photo",
            key="profile_remove_photo",
            disabled=image_field is None or not bool(current_photo),
        )
        save_profile = st.form_submit_button("Save profile", use_container_width=True)

    if uploaded_photo is not None:
        st.caption("New photo preview")
        st.image(uploaded_photo, width=180)

    if save_profile:
        clean_name = profile_name.strip()
        if not clean_name:
            st.warning("Full name is required.")
        elif uploaded_photo is not None and remove_photo:
            st.warning("Choose either a new photo upload or remove the current photo.")
        elif not profile_record.get("id"):
            st.warning("We couldn't find your profile record ID.")
        else:
            updates = {"name": clean_name}
            if preference_field:
                updates[preference_field] = profile_preference
            if batting_preference_field:
                updates[batting_preference_field] = (
                    None if batting_preference == "not_set" else batting_preference
                )
            if bowling_preference_field:
                updates[bowling_preference_field] = (
                    None if bowling_preference == "not_set" else bowling_preference
                )
            if bio_field:
                updates[bio_field] = profile_bio.strip() or None

            if uploaded_photo is not None:
                image_bytes = uploaded_photo.getvalue()
                if len(image_bytes) > MAX_PROFILE_IMAGE_BYTES:
                    st.warning("Profile photo must be 2MB or smaller.")
                    updates = None
                elif image_field:
                    updates[image_field] = _profile_image_to_data_uri(uploaded_photo)
            elif remove_photo and image_field:
                updates[image_field] = None

            if updates is not None:
                resp_profile = _execute_query(
                    supabase.table("registrations")
                    .update(updates)
                    .eq("id", profile_record["id"]),
                    action="update_profile",
                    user_message="We couldn't update your profile right now. Please try again.",
                )
                if resp_profile is not None:
                    _debug_action(
                        "update_profile",
                        [resp_profile],
                        context=f"id={profile_record['id']} email={email}",
                    )
                    st.success("Profile updated.")
                    st.cache_data.clear()
                    st.rerun()

missing_columns = []
if preference_field is None:
    missing_columns.append("preference")
if batting_preference_field is None:
    missing_columns.append("batting_preference")
if bowling_preference_field is None:
    missing_columns.append("bowling_preference")
if bio_field is None:
    missing_columns.append("bio")
if image_field is None:
    missing_columns.append("profile_photo_data")
if missing_columns:
    st.caption(
        "Database profile fields not found: "
        + ", ".join(missing_columns)
        + ". Add these columns to enable full profile editing."
    )
