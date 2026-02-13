import streamlit as st

from fixtures_page import render_fixture_page


st.set_page_config(
    page_title="Plucky M's Fixtures",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_fixture_page(
    team_key="plucky",
    heading="Plucky M's Fixtures",
    description="Confirm your availability for upcoming Plucky M's fixtures.",
    caption="update your availability here",
    empty_message="No Plucky M's fixtures are available right now.",
    default_fixture_label="Plucky M's Fixture",
)
