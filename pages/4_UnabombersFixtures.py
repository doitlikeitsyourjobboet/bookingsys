import streamlit as st

from fixtures_page import render_fixture_page


st.set_page_config(page_title="Unabombers Fixtures", layout="wide")

render_fixture_page(
    team_key="unabombers",
    heading="Unabombers Fixtures",
    description="Confirm your availabilityfor upcoming Unabombers fixtures.",
    caption="update your availability here",
    empty_message="No Unabombers fixtures are available right now.",
    default_fixture_label="Unabombers Fixture",
)
