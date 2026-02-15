import re

import streamlit as st

from booking_rules import AUTH_EMAIL_INPUT_KEY, AUTH_EMAIL_KEY


NAV_ITEMS = [
    {"key": "home", "label": "Login", "page": "Home.py"},
    {"key": "winter_nets", "label": "Nets", "page": "pages/2_WinterNets.py"},
    {"key": "fixtures", "label": "Fixtures", "page": "pages/3_Fixtures.py"},
    {"key": "profile", "label": "Profile", "page": "pages/1_Profile.py"},
]


TEAM_AFFILIATION_SESSION_KEY = "team_affiliation"
TEAM_AFFILIATION_FIELD_CANDIDATES = (
    "team_affiliation",
    "club_affiliation",
)
TEAM_AFFILIATION_OPTIONS = {
    "not_set": "Not set",
    "plucky": "Plucky M's",
    "unabombers": "Unabombers",
    "other": "Other",
}
TEAM_AFFILIATION_VALUES = tuple(TEAM_AFFILIATION_OPTIONS.keys())
TEAM_AFFILIATION_ALIASES = {
    "not_set": "",
    "none": "",
    "plucky": "plucky",
    "plucky_m_s": "plucky",
    "plucky_ms": "plucky",
    "pluckys": "plucky",
    "unabomber": "unabombers",
    "unabombers": "unabombers",
    "bomber": "unabombers",
    "bombers": "unabombers",
    "other": "other",
    "others": "other",
    "external": "other",
    "guest": "other",
}
TEAM_AFFILIATION_KEYS = {
    key for key in TEAM_AFFILIATION_VALUES if key != "not_set"
}
TEAM_AFFILIATION_CANONICAL_ORDER = tuple(
    key for key in TEAM_AFFILIATION_VALUES if key != "not_set"
)


def parse_team_affiliations(value) -> list[str]:
    raw_values: list[str] = []
    if isinstance(value, (list, tuple, set)):
        raw_values = [str(item) for item in value]
    else:
        raw_values = [str(value or "")]

    keys: list[str] = []
    for raw in raw_values:
        clean_raw = raw.strip().lower()
        if not clean_raw:
            continue

        normalized = clean_raw.replace("plucky m's", "plucky")
        normalized = normalized.replace(" and ", ",")
        normalized = re.sub(r"[&/|;+]", ",", normalized)
        parts = [
            part.strip().replace("-", "_").replace(" ", "_")
            for part in normalized.split(",")
            if part.strip()
        ]

        for part in parts:
            candidates = []
            if part in {"both", "all"}:
                candidates = ["plucky", "unabombers"]
            else:
                mapped = TEAM_AFFILIATION_ALIASES.get(part, part)
                if mapped:
                    candidates = [mapped]

            for candidate in candidates:
                if candidate in TEAM_AFFILIATION_KEYS and candidate not in keys:
                    keys.append(candidate)

        # Fallback heuristics for free-form values.
        if "plucky" in normalized and "plucky" not in keys:
            keys.append("plucky")
        if ("unabomb" in normalized or "bomber" in normalized) and "unabombers" not in keys:
            keys.append("unabombers")
        if "other" in normalized and "other" not in keys:
            keys.append("other")

    return keys


def normalize_team_affiliation(value) -> str:
    keys = parse_team_affiliations(value)
    if not keys:
        return ""
    ordered = [key for key in TEAM_AFFILIATION_CANONICAL_ORDER if key in keys]
    return ",".join(ordered)


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

    st.markdown(
        """
<style>
div[data-testid="stSegmentedControl"] [role="radiogroup"] {
  gap: 0.08rem;
  flex-wrap: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}
div[data-testid="stSegmentedControl"] [role="radio"] {
  padding-left: 0.44rem;
  padding-right: 0.44rem;
  white-space: nowrap;
  flex: 0 0 auto;
}
@media (max-width: 640px) {
  div[data-testid="stSegmentedControl"] [role="radio"] {
    font-size: 0.82rem;
    padding-left: 0.34rem;
    padding-right: 0.34rem;
  }
}
</style>
""",
        unsafe_allow_html=True,
    )

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

    st.divider()

def render_logout_footer(current_page: str) -> None:
    if not st.session_state.get("logged_in"):
        return

    st.divider()

    actions_col, _ = st.columns([1.6, 8.4], gap="small")
    with actions_col:
        if st.button(
            "Log out",
            key=f"footer_logout_{current_page}",
            type="primary",
        ):
            _clear_auth_state()
            st.switch_page("Home.py")

        if current_page != "admin":
            if st.button(
                "Admin",
                key=f"footer_admin_{current_page}",
            ):
                st.switch_page("pages/20_Admin.py")
