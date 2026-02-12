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


LEFT_LOGO_PATH = Path("visuals/pluckys.png")
RIGHT_LOGO_PATH = Path("visuals/bombers.png")


def _clear_auth_state() -> None:
    st.session_state.pop(AUTH_EMAIL_KEY, None)
    st.session_state.pop(AUTH_EMAIL_INPUT_KEY, None)
    st.session_state.pop("logged_in", None)
    st.session_state.pop("last_debug", None)
    st.session_state.pop("allowed_sync_attempted", None)
    st.session_state.pop("just_registered", None)
    st.session_state.pop("do_logout", None)
    st.session_state.pop("welcome_name", None)


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
    show_logout = bool(st.session_state.get("logged_in"))

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
div[data-testid="stButton"] button[kind="primary"] {
  min-height: 2.35rem;
}
</style>
""",
        unsafe_allow_html=True,
    )

    logo_left_col, nav_col, actions_col, logo_right_col = st.columns(
        [0.6, 6.8, 2.6, 0.6],
        gap="small",
    )

    with logo_left_col:
        if LEFT_LOGO_PATH.exists():
            st.image(str(LEFT_LOGO_PATH), width=52)

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

    with actions_col:
        welcome_col, logout_col = st.columns([1.4, 1.2], gap="small")

        with welcome_col:
            if welcome_text:
                st.markdown(
                    f"<div class='nav-welcome'>{welcome_text}</div>",
                    unsafe_allow_html=True,
                )

        with logout_col:
            if show_logout and st.button(
                "Log out",
                key=f"nav_logout_{current_page}",
                use_container_width=True,
                type="primary",
            ):
                _clear_auth_state()
                st.switch_page("Home.py")

    with logo_right_col:
        if RIGHT_LOGO_PATH.exists():
            st.image(str(RIGHT_LOGO_PATH), width=52)

    st.divider()
