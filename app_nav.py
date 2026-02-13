import re
from pathlib import Path

import streamlit as st

from booking_rules import AUTH_EMAIL_INPUT_KEY, AUTH_EMAIL_KEY


NAV_ITEMS = [
    {"key": "home", "label": "Login", "page": "Home.py"},
    {"key": "winter_nets", "label": "Nets", "page": "pages/2_WinterNets.py"},
    {"key": "plucky_fixtures", "label": "Plucky", "page": "pages/3_PluckyFixtures.py"},
    {
        "key": "unabombers_fixtures",
        "label": "Bombers",
        "page": "pages/4_UnabombersFixtures.py",
    },
    {"key": "profile", "label": "Profile", "page": "pages/1_Profile.py"},
]


TEAM_AFFILIATION_SESSION_KEY = "team_affiliation"
TEAM_AFFILIATION_FIELD_CANDIDATES = (
    "team_affiliation",
    "club_affiliation",
)
TEAM_AFFILIATION_OPTIONS = {
    "not_set": "Not set",
    "plucky": "Plucky",
    "unabombers": "Unabombers",
}
TEAM_AFFILIATION_VALUES = tuple(TEAM_AFFILIATION_OPTIONS.keys())
TEAM_AFFILIATION_ALIASES = {
    "not_set": "",
    "none": "",
    "plucky": "plucky",
    "pluckys": "plucky",
    "unabomber": "unabombers",
    "unabombers": "unabombers",
    "bomber": "unabombers",
    "bombers": "unabombers",
}
TEAM_AFFILIATION_LOGO_PATHS = {
    "plucky": Path("visuals/pluckys.png"),
    "unabombers": Path("visuals/bombers.png"),
}


def normalize_team_affiliation(value: str | None) -> str:
    clean_value = str(value or "").strip().lower()
    if not clean_value:
        return ""
    clean_value = clean_value.replace("-", "_").replace(" ", "_")
    if clean_value in TEAM_AFFILIATION_ALIASES:
        clean_value = TEAM_AFFILIATION_ALIASES[clean_value]
    if clean_value in TEAM_AFFILIATION_LOGO_PATHS:
        return clean_value
    return ""


def sync_team_affiliation(registration_record: dict | None) -> bool:
    if not isinstance(registration_record, dict):
        return False

    field_name = next(
        (
            candidate
            for candidate in TEAM_AFFILIATION_FIELD_CANDIDATES
            if candidate in registration_record
        ),
        None,
    )
    if not field_name:
        return False

    normalized = normalize_team_affiliation(registration_record.get(field_name))
    existing = normalize_team_affiliation(
        st.session_state.get(TEAM_AFFILIATION_SESSION_KEY)
    )
    if normalized == existing:
        return False

    st.session_state[TEAM_AFFILIATION_SESSION_KEY] = normalized
    return True


def _clear_auth_state() -> None:
    st.session_state.pop(AUTH_EMAIL_KEY, None)
    st.session_state.pop(AUTH_EMAIL_INPUT_KEY, None)
    st.session_state.pop("logged_in", None)
    st.session_state.pop("last_debug", None)
    st.session_state.pop("allowed_sync_attempted", None)
    st.session_state.pop("just_registered", None)
    st.session_state.pop("do_logout", None)
    st.session_state.pop("welcome_name", None)
    st.session_state.pop("admin_authed", None)
    st.session_state.pop(TEAM_AFFILIATION_SESSION_KEY, None)


def _derive_welcome_text() -> str:
    if not st.session_state.get("logged_in"):
        return ""

    stored_name = str(st.session_state.get("welcome_name") or "").strip()
    if stored_name:
        return f"Welcome, {stored_name}"

    email = str(st.session_state.get(AUTH_EMAIL_KEY) or "").strip().lower()
    if not email:
        return "Welcome"

    email_local = email.split("@", 1)[0]
    normalized = re.sub(r"[._-]+", " ", email_local).strip()
    if not normalized:
        return "Welcome"
    return f"Welcome, {normalized.title()}"


def render_compact_nav(current_page: str, *, include_admin: bool = False) -> None:
    items = list(NAV_ITEMS)
    if include_admin:
        items.append({"key": "admin", "label": "Admin", "page": "pages/20_Admin.py"})

    label_to_page = {item["label"]: item["page"] for item in items}
    labels = [item["label"] for item in items]
    current_label = next(
        (item["label"] for item in items if item["key"] == current_page),
        labels[0],
    )
    nav_key = f"compact_nav_{current_page}_{'admin' if include_admin else 'main'}"

    welcome_text = _derive_welcome_text()
    affiliation_key = normalize_team_affiliation(
        st.session_state.get(TEAM_AFFILIATION_SESSION_KEY)
    )
    affiliation_logo = TEAM_AFFILIATION_LOGO_PATHS.get(affiliation_key)

    st.markdown(
        """
<style>
div[data-testid="stSegmentedControl"] [role="radiogroup"] {
  gap: 0.08rem;
}
div[data-testid="stSegmentedControl"] [role="radio"] {
  padding-left: 0.48rem;
  padding-right: 0.48rem;
}
.nav-welcome {
  font-size: 0.98rem;
  font-weight: 600;
  line-height: 2.35rem;
  white-space: nowrap;
}
</style>
""",
        unsafe_allow_html=True,
    )

    nav_col, welcome_col = st.columns(
        [7.8, 2.2],
        gap="small",
    )

    with nav_col:
        selection = st.segmented_control(
            "Navigate",
            options=labels,
            default=current_label,
            selection_mode="single",
            label_visibility="collapsed",
            key=nav_key,
            width="stretch",
        )

        if selection and selection != current_label:
            st.switch_page(label_to_page[selection])

    with welcome_col:
        if welcome_text:
            if affiliation_logo and affiliation_logo.exists():
                logo_col, text_col = st.columns([0.45, 1.55], gap="small")
                with logo_col:
                    st.image(str(affiliation_logo), width=44)
                with text_col:
                    st.markdown(
                        f"<div class='nav-welcome'>{welcome_text}</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    f"<div class='nav-welcome'>{welcome_text}</div>",
                    unsafe_allow_html=True,
                )

def render_logout_footer(current_page: str) -> None:
    if not st.session_state.get("logged_in"):
        return

    st.divider()
    _, logout_col = st.columns([8.5, 1.5], gap="small")
    with logout_col:
        if st.button(
            "Log out",
            key=f"footer_logout_{current_page}",
            use_container_width=True,
            type="primary",
        ):
            _clear_auth_state()
            st.switch_page("Home.py")
