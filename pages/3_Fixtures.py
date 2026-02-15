import streamlit as st

from fixtures_page import render_fixture_page


st.set_page_config(
    page_title="Fixtures",
    layout="wide",
    initial_sidebar_state="collapsed",
)

TEAM_CONFIGS = {
    "Plucky M's": {
        "team_key": "plucky",
        "heading": "Plucky M's Fixtures",
        "description": "Confirm your availability for upcoming Plucky M's fixtures.",
        "caption": "Update your availability here.",
        "empty_message": "No Plucky M's fixtures are available right now.",
        "default_fixture_label": "Plucky M's Fixture",
    },
    "Unabombers": {
        "team_key": "unabombers",
        "heading": "Unabombers Fixtures",
        "description": "Confirm your availability for upcoming Unabombers fixtures.",
        "caption": "Update your availability here.",
        "empty_message": "No Unabombers fixtures are available right now.",
        "default_fixture_label": "Unabombers Fixture",
    },
}

render_fixture_page(
    team_key="plucky",
    heading="Fixtures",
    description="Confirm your availability for upcoming fixtures.",
    caption="Update your availability here.",
    empty_message="No fixtures are available right now.",
    default_fixture_label="Fixture",
    team_options=TEAM_CONFIGS,
)
