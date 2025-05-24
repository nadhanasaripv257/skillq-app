import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=st.secrets["SUPABASE_URL"],
    supabase_key=st.secrets["SUPABASE_KEY"]
)

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'needs_verification' not in st.session_state:
        st.session_state.needs_verification = False

def signup_user(email: str, password: str) -> bool:
    """Attempt to sign up user with Supabase"""
    try:
        # Using the correct method for Supabase v1.2.0
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        # Check if we have a user in the response
        if hasattr(response, 'user') and response.user:
            st.session_state.authenticated = True
            st.session_state.user_email = email
            st.session_state.needs_verification = True
            return True
        else:
            st.error("Failed to create account")
            return False
    except Exception as e:
        st.error(f"Signup failed: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="SkillQ - Sign Up",
        page_icon="📝",
        layout="centered"
    )
    
    initialize_session_state()
    
    # If user is already authenticated, show appropriate message
    if st.session_state.authenticated:
        if st.session_state.needs_verification:
            st.success(f"Welcome to SkillQ, {st.session_state.user_email}!")
            st.info("Please check your email to verify your account.")
            if st.button("Back to Login"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.needs_verification = False
                st.switch_page("login.py")
        else:
            st.success(f"Welcome to SkillQ, {st.session_state.user_email}!")
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.needs_verification = False
                st.rerun()
        return

    # Signup form
    st.title("📝 SkillQ Sign Up")
    
    with st.form("signup_form"):
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm your password")
        submit = st.form_submit_button("Sign Up")
        
        if submit:
            if not email or not password or not confirm_password:
                st.error("Please fill in all fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters long")
            else:
                if signup_user(email, password):
                    st.rerun()
    
    # Login link
    st.markdown("---")
    if st.button("Already have an account? Login here"):
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 