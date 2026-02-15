#v2.15

import base64
import json
from datetime import date
from pathlib import Path

import streamlit as st
from supabase import create_client

from app_nav import (
    TEAM_AFFILIATION_FIELD_CANDIDATES,
    TEAM_AFFILIATION_OPTIONS,
    TEAM_AFFILIATION_SESSION_KEY,
    TEAM_AFFILIATION_VALUES,
    normalize_team_affiliation,
    parse_team_affiliations,
    render_compact_nav,
    render_logout_footer,
    sync_team_affiliation,
)
from booking_rules import AUTH_EMAIL_KEY, normalize_email


st.set_page_config(
    page_title="My Profile",
    layout="wide",
    initial_sidebar_state="collapsed",
)
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

DEBUG = _secret_bool("DEBUG_MODE")

PROFILE_PREFERENCE_OPTIONS = {
    "bowling": "Bowling",
    "batting": "Batting",
    "both": "All Rounder",
}
PROFILE_PREFERENCE_VALUES = tuple(PROFILE_PREFERENCE_OPTIONS.keys())
PROFILE_PREFERENCE_FIELD_CANDIDATES = (
    "preference",
    "playing_preference",
    "player_preference",
)
PROFILE_AFFILIATION_OPTIONS = TEAM_AFFILIATION_OPTIONS
PROFILE_AFFILIATION_VALUES = TEAM_AFFILIATION_VALUES

PROFILE_CORE_FIELDS = {
    "player_id": "UUID",
    "full_name": "String",
    "nickname": "String",
    "email": "String",
    "date_of_birth": "Date",
}

PROFILE_CORE_FIELD_CANDIDATES = {
    "player_id": ("player_id", "id"),
    "full_name": ("full_name", "name"),
    "nickname": ("nickname",),
    "email": ("email",),
    "date_of_birth": ("date_of_birth", "dob"),
}

PROFILE_BATTING_HAND_OPTIONS = {
    "not_set": "Not set",
    "right": "Right Hand Bat",
    "left": "Left Hand Bat",
}

PROFILE_BATTING_ROLE_OPTIONS = {
    "not_set": "Not set",
    "opener": "Opener",
    "top_order": "Top Order",
    "middle_order": "Middle Order",
    "finisher": "Finisher",
    "all_rounder": "All-Rounder",
    "wicketkeeper": "Wicketkeeper Batter",
    "tailender": "Tailender",
}

PROFILE_BATTING_STYLE_OPTIONS = {
    "orthodox": "Orthodox",
    "unorthodox": "Unorthodox",
    "aggressive": "Aggressive",
    "defensive": "Defensive",
    "power_hitter": "Power Hitter",
    "anchor": "Anchor",
    "improvisational": "Improvisational",
    "360": "360 Player",
}

PROFILE_BATTING_PREFERENCE_OPTIONS = PROFILE_BATTING_ROLE_OPTIONS
PROFILE_BATTING_PREFERENCE_VALUES = tuple(PROFILE_BATTING_ROLE_OPTIONS.keys())
PROFILE_BATTING_PREFERENCE_FIELD_CANDIDATES = (
    "batting_preference",
    "batting_role",
    "batting_style",
)
PROFILE_BATTING_ROLE_ALIASES = {
    "authox": "top_order",
    "orthodx": "top_order",
    "orthodox": "top_order",
    "slogger": "finisher",
    "pinch_hitter": "finisher",
    "power_hitter": "finisher",
    "anchor": "top_order",
    "accumulator": "middle_order",
    "switch_hitter": "middle_order",
    "top-order": "top_order",
    "toporder": "top_order",
    "middle-order": "middle_order",
    "middleorder": "middle_order",
    "all-rounder": "all_rounder",
    "allrounder": "all_rounder",
    "wicket_keeper": "wicketkeeper",
    "keeper": "wicketkeeper",
    "wk": "wicketkeeper",
}
PROFILE_BATTING_PREFERENCE_ALIASES = PROFILE_BATTING_ROLE_ALIASES
PROFILE_BATTING_STYLE_ALIASES = {
    "power hitter": "power_hitter",
    "360_player": "360",
}

PROFILE_BOWLING_ARM_OPTIONS = {
    "not_set": "Not set",
    "right": "Right Arm",
    "left": "Left Arm",
}

PROFILE_BOWLING_TYPE_OPTIONS = {
    "not_set": "Not set",

    # Pace
    "fast": "Fast",
    "fast_medium": "Fast-Medium",
    "medium_fast": "Medium-Fast",
    "medium": "Medium",
    "slow_medium": "Slow Medium",

    # Spin - Finger
    "off_spin": "Off Spin",
    "leg_spin": "Leg Spin",
    "left_arm_orthodox": "Left Arm Orthodox",
    "left_arm_wrist_spin": "Left Arm Wrist Spin",

    # Specialist
    "mystery_spin": "Mystery Spinner",
}

PROFILE_BOWLING_TRAITS = {
    "swing": "Swing",
    "reverse_swing": "Reverse Swing",
    "seam": "Seam",
    "cutters": "Cutters",
    "yorker_specialist": "Yorker Specialist",
    "bouncer_specialist": "Bouncer Specialist",
    "death_bowler": "Death Overs Specialist",
    "powerplay_bowler": "Powerplay Specialist",
}

PROFILE_BOWLING_PREFERENCE_OPTIONS = PROFILE_BOWLING_TYPE_OPTIONS
PROFILE_BOWLING_PREFERENCE_VALUES = tuple(PROFILE_BOWLING_TYPE_OPTIONS.keys())
PROFILE_BOWLING_PREFERENCE_FIELD_CANDIDATES = (
    "bowling_preference",
    "bowling_type",
    "bowling_style",
)
PROFILE_BOWLING_TYPE_ALIASES = {
    "right-arm": "medium",
    "rightarm": "medium",
    "left-arm": "medium",
    "leftarm": "medium",
    "offspin": "off_spin",
    "legspin": "leg_spin",
    "right_arm_fast": "fast",
    "right_arm_fast_medium": "fast_medium",
    "right_arm_medium_fast": "medium_fast",
    "right_arm_medium": "medium",
    "left_arm_fast": "fast",
    "left_arm_fast_medium": "fast_medium",
    "left_arm_medium_fast": "medium_fast",
    "left_arm_medium": "medium",
    "right_arm_off_spin": "off_spin",
    "right_arm_leg_spin": "leg_spin",
}
PROFILE_BOWLING_PREFERENCE_ALIASES = PROFILE_BOWLING_TYPE_ALIASES

PROFILE_OVERS_PHASE_OPTIONS = {
    "not_set": "Not set",
    "powerplay": "Powerplay",
    "middle": "Middle Overs",
    "death": "Death Overs",
}

PROFILE_FIELDING_OPTIONS = {
    "primary_position": [
        "Slip",
        "Gully",
        "Point",
        "Cover",
        "Mid-Off",
        "Mid-On",
        "Mid-Wicket",
        "Fine Leg",
        "Third Man",
        "Long On",
        "Long Off",
        "Wicketkeeper",
    ]
}
PROFILE_FIELDING_POSITION_OPTIONS = ("not_set",) + tuple(
    PROFILE_FIELDING_OPTIONS["primary_position"]
)
PROFILE_BATTING_POSITION_OPTIONS = ("not_set",) + tuple(str(v) for v in range(1, 12))

PROFILE_ADVANCED_FIELD_CANDIDATES = {
    "batting_hand": ("batting_hand",),
    "batting_style_traits": ("batting_style_traits", "batting_styles", "batting_traits"),
    "preferred_batting_position": ("preferred_batting_position",),
    "bowling_arm": ("bowling_arm",),
    "bowling_traits": ("bowling_traits",),
    "preferred_overs_phase": ("preferred_overs_phase",),
    "primary_position": ("primary_position", "primary_fielding_position"),
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
AFFILIATION_LOGO_PATHS = {
    "plucky": Path("visuals/pluckys.png"),
    "unabombers": Path("visuals/bombers.png"),
}

PROFILE_AFFILIATION_SCHEMA_HINT = (
    "The team affiliation value was rejected by the database. "
    "Add/update `team_affiliation` using the SQL in README.md and try again."
)
PROFILE_BATTING_SCHEMA_HINT = (
    "The batting role value was rejected by the database. "
    "Update `batting_preference` check values using the SQL in README.md and try again."
)
PROFILE_BOWLING_SCHEMA_HINT = (
    "The bowling style value was rejected by the database. "
    "Update `bowling_preference` check values using the SQL in README.md and try again."
)


def _profile_update_failure_message(error: Exception | str) -> str:
    text = str(error).lower()
    if "batting_preference" in text and (
        "violates check constraint" in text
        or "invalid input value" in text
        or "value too long" in text
        or "does not exist" in text
    ):
        return PROFILE_BATTING_SCHEMA_HINT
    if "bowling_preference" in text and (
        "violates check constraint" in text
        or "invalid input value" in text
        or "value too long" in text
        or "does not exist" in text
    ):
        return PROFILE_BOWLING_SCHEMA_HINT
    if "team_affiliation" in text and (
        "violates check constraint" in text
        or "invalid input value" in text
        or "value too long" in text
        or "does not exist" in text
    ):
        return PROFILE_AFFILIATION_SCHEMA_HINT
    if "violates check constraint" in text:
        return (
            "One of the selected profile values was rejected by the database. "
            "Update profile constraints using README.md and try again."
        )
    return "We couldn't update your profile right now. Please try again."


def _execute_query(
    query,
    action: str,
    user_message: str,
    *,
    custom_error_message=None,
    show_error_details: bool = False,
):
    try:
        return query.execute()
    except Exception as exc:
        if DEBUG:
            st.session_state.last_debug = f"Action: {action}\n\nError:\n{exc}"
            st.error(f"{action} failed")
            st.code(str(exc))
        if callable(custom_error_message):
            st.error(custom_error_message(exc))
        else:
            st.error(user_message)
        if show_error_details or DEBUG:
            st.caption("Error details")
            st.code(str(exc), language="text")
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


def _normalize_profile_multi_choice(
    value,
    allowed_values: tuple[str, ...],
    *,
    aliases: dict[str, str] | None = None,
) -> list[str]:
    raw_items: list[str] = []

    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw = str(value or "").strip()
        if raw:
            if raw.startswith("[") and raw.endswith("]"):
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = None
                if isinstance(parsed, list):
                    raw_items = [str(item) for item in parsed]
                else:
                    raw_items = [item.strip() for item in raw.split(",") if item.strip()]
            else:
                raw_items = [item.strip() for item in raw.split(",") if item.strip()]

    selected: list[str] = []
    for item in raw_items:
        normalized = _normalize_profile_choice(
            item,
            allowed_values,
            default="",
            aliases=aliases,
        )
        if normalized and normalized not in selected:
            selected.append(normalized)
    return selected


def _serialize_profile_multi_choice(values: list[str]) -> str | None:
    if not values:
        return None
    selected = [str(value).strip() for value in values if str(value).strip()]
    return ",".join(selected) if selected else None


def _normalize_fielding_positions(value) -> list[str]:
    allowed = list(PROFILE_FIELDING_OPTIONS["primary_position"])
    allowed_lookup = {
        item.strip().lower().replace("-", " ").replace("_", " "): item
        for item in allowed
    }

    raw_items: list[str] = []
    if isinstance(value, (list, tuple, set)):
        raw_items = [str(item) for item in value]
    else:
        raw = str(value or "").strip()
        if raw:
            raw_items = [item.strip() for item in raw.split(",") if item.strip()]

    selected: list[str] = []
    for item in raw_items:
        key = item.strip().lower().replace("-", " ").replace("_", " ")
        canonical = allowed_lookup.get(key)
        if canonical and canonical not in selected:
            selected.append(canonical)
    return selected


def _parse_profile_date(value) -> date | None:
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except Exception:
        return None


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _choice_index(options: list[str] | tuple[str, ...], value: str, default: int = 0) -> int:
    try:
        return list(options).index(value)
    except ValueError:
        return default


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
    "Update your identity, team affiliation, batting and bowling profiles, fielding position, and profile photo."
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
core_fields = {
    key: _first_existing_field(profile_record, candidates)
    for key, candidates in PROFILE_CORE_FIELD_CANDIDATES.items()
}
advanced_fields = {
    key: _first_existing_field(profile_record, candidates)
    for key, candidates in PROFILE_ADVANCED_FIELD_CANDIDATES.items()
}
name_field = core_fields["full_name"] or ("name" if "name" in profile_record else None)
profile_name_for_header = _as_text(
    profile_record.get(name_field) if name_field else profile_record.get("name")
).strip()
if profile_name_for_header and st.session_state.get("welcome_name") != profile_name_for_header:
    st.session_state["welcome_name"] = profile_name_for_header

preference_field = _first_existing_field(
    profile_record, PROFILE_PREFERENCE_FIELD_CANDIDATES
)
affiliation_field = _first_existing_field(
    profile_record, TEAM_AFFILIATION_FIELD_CANDIDATES
)
batting_preference_field = _first_existing_field(
    profile_record, PROFILE_BATTING_PREFERENCE_FIELD_CANDIDATES
)
bowling_preference_field = _first_existing_field(
    profile_record, PROFILE_BOWLING_PREFERENCE_FIELD_CANDIDATES
)
bio_field = _first_existing_field(profile_record, PROFILE_BIO_FIELD_CANDIDATES)
image_field = _first_existing_field(profile_record, PROFILE_IMAGE_FIELD_CANDIDATES)

player_id_field = core_fields["player_id"]
nickname_field = core_fields["nickname"]
email_field = core_fields["email"]
dob_field = core_fields["date_of_birth"]

batting_hand_field = advanced_fields["batting_hand"]
batting_style_traits_field = advanced_fields["batting_style_traits"]
preferred_batting_position_field = advanced_fields["preferred_batting_position"]
bowling_arm_field = advanced_fields["bowling_arm"]
bowling_traits_field = advanced_fields["bowling_traits"]
preferred_overs_phase_field = advanced_fields["preferred_overs_phase"]
primary_position_field = advanced_fields["primary_position"]

if DEBUG:
    st.caption(
        "Team affiliation field: "
        + (affiliation_field if affiliation_field else "not found")
    )

if sync_team_affiliation(profile_record):
    st.rerun()

saved_preference = _normalize_profile_preference(
    profile_record.get(preference_field) if preference_field else None
)
saved_preference_index = PROFILE_PREFERENCE_VALUES.index(saved_preference)
saved_affiliation_values = parse_team_affiliations(
    profile_record.get(affiliation_field) if affiliation_field else None
)
affiliation_logo_paths = [
    str(AFFILIATION_LOGO_PATHS[key])
    for key in saved_affiliation_values
    if key in AFFILIATION_LOGO_PATHS and AFFILIATION_LOGO_PATHS[key].exists()
]
has_other_affiliation = "other" in saved_affiliation_values
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

batting_hand_values = list(PROFILE_BATTING_HAND_OPTIONS.keys())
saved_batting_hand = _normalize_profile_choice(
    profile_record.get(batting_hand_field) if batting_hand_field else None,
    tuple(batting_hand_values),
    default="not_set",
)
saved_batting_hand_index = _choice_index(batting_hand_values, saved_batting_hand)

saved_batting_styles = _normalize_profile_multi_choice(
    profile_record.get(batting_style_traits_field) if batting_style_traits_field else None,
    tuple(PROFILE_BATTING_STYLE_OPTIONS.keys()),
    aliases=PROFILE_BATTING_STYLE_ALIASES,
)

bowling_arm_values = list(PROFILE_BOWLING_ARM_OPTIONS.keys())
saved_bowling_arm = _normalize_profile_choice(
    profile_record.get(bowling_arm_field) if bowling_arm_field else None,
    tuple(bowling_arm_values),
    default="not_set",
)
saved_bowling_arm_index = _choice_index(bowling_arm_values, saved_bowling_arm)

saved_bowling_traits = _normalize_profile_multi_choice(
    profile_record.get(bowling_traits_field) if bowling_traits_field else None,
    tuple(PROFILE_BOWLING_TRAITS.keys()),
)

overs_phase_values = list(PROFILE_OVERS_PHASE_OPTIONS.keys())
saved_overs_phase = _normalize_profile_choice(
    profile_record.get(preferred_overs_phase_field) if preferred_overs_phase_field else None,
    tuple(overs_phase_values),
    default="not_set",
)
saved_overs_phase_index = _choice_index(overs_phase_values, saved_overs_phase)

saved_batting_position = _normalize_profile_choice(
    profile_record.get(preferred_batting_position_field)
    if preferred_batting_position_field
    else None,
    PROFILE_BATTING_POSITION_OPTIONS,
    default="not_set",
)
saved_batting_position_index = _choice_index(
    PROFILE_BATTING_POSITION_OPTIONS, saved_batting_position
)

fielding_position_options = list(PROFILE_FIELDING_OPTIONS["primary_position"])
saved_primary_positions = _normalize_fielding_positions(
    profile_record.get(primary_position_field) if primary_position_field else None
)
current_photo = _decode_profile_image(
    profile_record.get(image_field) if image_field else None
)

form_col, image_col = st.columns([2, 1])
with image_col:
    st.caption("Profile photo")
    if current_photo:
        st.image(current_photo, width=180)
    else:
        st.info("No photo uploaded.")

    st.caption("Team logos")
    if affiliation_logo_paths:
        st.image(affiliation_logo_paths, width=88)
    if has_other_affiliation:
        st.caption("Other")
    if not affiliation_logo_paths and not has_other_affiliation:
        st.info("No team selected.")

with form_col:
    with st.form("profile_form", clear_on_submit=False):
        st.markdown("#### Identity")
        st.text_input(
            "Player ID",
            value=_as_text(
                profile_record.get(player_id_field)
                if player_id_field
                else profile_record.get("id")
            ),
            key="profile_player_id_display",
            disabled=True,
        )
        profile_name = st.text_input(
            "Full name",
            value=_as_text(profile_record.get(name_field) if name_field else ""),
            key="profile_name_input",
            disabled=name_field is None and "name" not in profile_record,
        )
        profile_nickname = st.text_input(
            "Nickname",
            value=_as_text(profile_record.get(nickname_field) if nickname_field else ""),
            key="profile_nickname_input",
            disabled=nickname_field is None,
        )
        st.text_input(
            "Email",
            value=_as_text(profile_record.get(email_field) if email_field else email),
            key="profile_email_display",
            disabled=True,
        )
        profile_dob = st.text_input(
            "Date of birth (YYYY-MM-DD)",
            value=_as_text(profile_record.get(dob_field) if dob_field else "")[:10],
            key="profile_dob_input",
            disabled=dob_field is None,
        )
        st.markdown("#### Team & Preference")
        profile_preference = st.selectbox(
            "Preference",
            options=list(PROFILE_PREFERENCE_VALUES),
            index=saved_preference_index,
            format_func=lambda value: PROFILE_PREFERENCE_OPTIONS[value],
            key="profile_preference_input",
            disabled=preference_field is None,
        )
        profile_affiliation = st.multiselect(
            "Team affiliation",
            options=[value for value in PROFILE_AFFILIATION_VALUES if value != "not_set"],
            default=saved_affiliation_values,
            format_func=lambda value: PROFILE_AFFILIATION_OPTIONS[value],
            key="profile_affiliation_input",
            disabled=affiliation_field is None,
        )
        st.markdown("#### Batting Profile")
        batting_hand = st.selectbox(
            "Batting hand",
            options=batting_hand_values,
            index=saved_batting_hand_index,
            format_func=lambda value: PROFILE_BATTING_HAND_OPTIONS[value],
            key="profile_batting_hand_input",
            disabled=batting_hand_field is None,
        )
        batting_preference = st.selectbox(
            "Batting role",
            options=list(PROFILE_BATTING_PREFERENCE_VALUES),
            index=saved_batting_preference_index,
            format_func=lambda value: PROFILE_BATTING_PREFERENCE_OPTIONS[value],
            key="profile_batting_preference_input",
            disabled=batting_preference_field is None,
        )
        batting_styles = st.multiselect(
            "Batting style traits",
            options=list(PROFILE_BATTING_STYLE_OPTIONS.keys()),
            default=saved_batting_styles,
            format_func=lambda value: PROFILE_BATTING_STYLE_OPTIONS[value],
            key="profile_batting_styles_input",
            disabled=batting_style_traits_field is None,
        )
        preferred_batting_position = st.selectbox(
            "Preferred batting position",
            options=list(PROFILE_BATTING_POSITION_OPTIONS),
            index=saved_batting_position_index,
            format_func=lambda value: "Not set" if value == "not_set" else value,
            key="profile_batting_position_input",
            disabled=preferred_batting_position_field is None,
        )
        st.markdown("#### Bowling Profile")
        bowling_arm = st.selectbox(
            "Bowling arm",
            options=bowling_arm_values,
            index=saved_bowling_arm_index,
            format_func=lambda value: PROFILE_BOWLING_ARM_OPTIONS[value],
            key="profile_bowling_arm_input",
            disabled=bowling_arm_field is None,
        )
        bowling_preference = st.selectbox(
            "Bowling type",
            options=list(PROFILE_BOWLING_PREFERENCE_VALUES),
            index=saved_bowling_preference_index,
            format_func=lambda value: PROFILE_BOWLING_PREFERENCE_OPTIONS[value],
            key="profile_bowling_preference_input",
            disabled=bowling_preference_field is None,
        )
        bowling_traits = st.multiselect(
            "Bowling traits",
            options=list(PROFILE_BOWLING_TRAITS.keys()),
            default=saved_bowling_traits,
            format_func=lambda value: PROFILE_BOWLING_TRAITS[value],
            key="profile_bowling_traits_input",
            disabled=bowling_traits_field is None,
        )
        preferred_overs_phase = st.selectbox(
            "Preferred overs phase",
            options=overs_phase_values,
            index=saved_overs_phase_index,
            format_func=lambda value: PROFILE_OVERS_PHASE_OPTIONS[value],
            key="profile_overs_phase_input",
            disabled=preferred_overs_phase_field is None,
        )
        st.markdown("#### Fielding Profile")
        primary_positions = st.multiselect(
            "Preferred fielding positions",
            options=fielding_position_options,
            default=saved_primary_positions,
            key="profile_primary_position_input",
            disabled=primary_position_field is None,
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
            updates: dict[str, object] | None = {}
            if "name" in profile_record:
                updates["name"] = clean_name
            if "full_name" in profile_record:
                updates["full_name"] = clean_name
            if name_field and name_field not in {"name", "full_name"}:
                updates[name_field] = clean_name

            if nickname_field:
                updates[nickname_field] = profile_nickname.strip() or None
            if dob_field:
                dob_value = profile_dob.strip()
                if dob_value:
                    parsed_dob = _parse_profile_date(dob_value)
                    if parsed_dob is None:
                        st.warning("Date of birth must be in YYYY-MM-DD format.")
                        updates = None
                    else:
                        updates[dob_field] = parsed_dob.isoformat()
                else:
                    updates[dob_field] = None

            if updates is not None and preference_field:
                updates[preference_field] = profile_preference
            if updates is not None and affiliation_field:
                normalized_affiliation = normalize_team_affiliation(profile_affiliation)
                updates[affiliation_field] = normalized_affiliation or None

            if updates is not None and batting_hand_field:
                updates[batting_hand_field] = (
                    None if batting_hand == "not_set" else batting_hand
                )
            if updates is not None and batting_preference_field:
                updates[batting_preference_field] = (
                    None if batting_preference == "not_set" else batting_preference
                )
            if updates is not None and batting_style_traits_field:
                updates[batting_style_traits_field] = _serialize_profile_multi_choice(
                    batting_styles
                )

            if updates is not None and bowling_arm_field:
                updates[bowling_arm_field] = (
                    None if bowling_arm == "not_set" else bowling_arm
                )
            if updates is not None and bowling_preference_field:
                updates[bowling_preference_field] = (
                    None if bowling_preference == "not_set" else bowling_preference
                )
            if updates is not None and bowling_traits_field:
                updates[bowling_traits_field] = _serialize_profile_multi_choice(
                    bowling_traits
                )
            if updates is not None and preferred_overs_phase_field:
                updates[preferred_overs_phase_field] = (
                    None if preferred_overs_phase == "not_set" else preferred_overs_phase
                )
            if updates is not None and preferred_batting_position_field:
                updates[preferred_batting_position_field] = (
                    None
                    if preferred_batting_position == "not_set"
                    else int(preferred_batting_position)
                )

            if updates is not None and primary_position_field:
                updates[primary_position_field] = _serialize_profile_multi_choice(
                    primary_positions
                )

            if updates is not None and bio_field:
                updates[bio_field] = profile_bio.strip() or None

            if uploaded_photo is not None:
                image_bytes = uploaded_photo.getvalue()
                if len(image_bytes) > MAX_PROFILE_IMAGE_BYTES:
                    st.warning("Profile photo must be 2MB or smaller.")
                    updates = None
                elif image_field and updates is not None:
                    updates[image_field] = _profile_image_to_data_uri(uploaded_photo)
            elif remove_photo and image_field and updates is not None:
                updates[image_field] = None

            if updates is not None:
                resp_profile = _execute_query(
                    supabase.table("registrations")
                    .update(updates)
                    .eq("id", profile_record["id"]),
                    action="update_profile",
                    user_message="We couldn't update your profile right now. Please try again.",
                    custom_error_message=_profile_update_failure_message,
                    show_error_details=True,
                )
                if resp_profile is not None:
                    _debug_action(
                        "update_profile",
                        [resp_profile],
                        context=f"id={profile_record['id']} email={email}",
                    )
                    if affiliation_field:
                        st.session_state[TEAM_AFFILIATION_SESSION_KEY] = (
                            normalize_team_affiliation(updates.get(affiliation_field))
                        )
                    st.success("Profile updated.")
                    st.cache_data.clear()
                    st.rerun()

missing_columns = []
if preference_field is None:
    missing_columns.append("preference")
if affiliation_field is None:
    missing_columns.append("team_affiliation")
if batting_preference_field is None:
    missing_columns.append("batting_preference")
if bowling_preference_field is None:
    missing_columns.append("bowling_preference")
if bio_field is None:
    missing_columns.append("bio")
if image_field is None:
    missing_columns.append("profile_photo_data")

for key, field_name in core_fields.items():
    if key == "player_id":
        continue
    if field_name is None:
        missing_columns.append(PROFILE_CORE_FIELD_CANDIDATES[key][0])

for key, field_name in advanced_fields.items():
    if field_name is None:
        missing_columns.append(PROFILE_ADVANCED_FIELD_CANDIDATES[key][0])

missing_columns = list(dict.fromkeys(missing_columns))
if missing_columns:
    with st.expander("Database profile fields not found", expanded=False):
        st.caption(", ".join(missing_columns))
        st.caption("Add these columns to enable full profile editing.")

render_logout_footer("profile")
