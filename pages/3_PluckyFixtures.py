import streamlit as st

from fixtures_page import render_fixture_page


st.set_page_config(
    page_title="Plucky Fixtures",
    layout="wide",
    initial_sidebar_state="collapsed",
)

render_fixture_page(
    team_key="plucky",
    heading="Plucky Fixtures",
    description="Confirm your availability for upcoming Plucky fixtures.",
    caption="update your availability here",
    empty_message="No Plucky fixtures are available right now.",
    default_fixture_label="Plucky Fixture",
)
