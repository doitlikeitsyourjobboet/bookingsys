import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Nets Booking", layout="centered")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

st.title("🏏 Nets Booking – Sessions")

st.info("Login is handled by Supabase Auth. For now, this page assumes you are authenticated.")

# Fetch sessions with availability
response = supabase.table("session_availability") \
    .select("*") \
    .order("start_at") \
    .execute()

if response.data:
    for s in response.data:
        st.write(
            f"**{s['start_at']}**  |  "
            f"Slots remaining: **{s['slots_remaining']}** / {s['capacity']}"
        )
else:
    st.warning("No sessions found.")
