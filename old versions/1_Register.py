import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Register", layout="centered")

supabase = create_client(
    st.secrets["SUPABASE_URL"],
    st.secrets["SUPABASE_ANON_KEY"],
)

st.title("🏏 Nets Booking – Register")

st.write("Register your details. Once approved, you’ll be able to book nets.")

name = st.text_input("Full name")
email = st.text_input("Email address").strip().lower()

if st.button("Register"):
    if not name or not email:
        st.warning("Please enter both name and email.")
        st.stop()

    try:
        supabase.table("registrations").insert({
            "name": name,
            "email": email,
        }).execute()

        st.success("Thanks! Your registration is pending approval.")
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg:
            st.info("This email is already registered.")
        else:
            st.error(f"Registration failed: {e}")
