import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, UTC

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=os.environ.get("SUPABASE_URL"),
    supabase_key=os.environ.get("SUPABASE_KEY")
)

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'needs_verification' not in st.session_state:
        st.session_state.needs_verification = False

def signup_user(email: str, password: str) -> bool:
    """Sign up a user and create a profile in user_profiles"""
    try:
        # Sign up user
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })

        if hasattr(response, 'user') and response.user:
            user_id = response.user.id
            access_token = response.session.access_token if response.session else None

            # Store session for redirect logic
            st.session_state.authenticated = True
            st.session_state.user_email = email
            st.session_state.user_id = user_id
            st.session_state.needs_verification = True

            # If no token, just stop here — user must verify email
            if not access_token:
                st.info("Please check your email to verify your account before logging in.")
                return True

            # Authenticated Supabase client
            supabase_authed = create_client(
                os.environ.get("SUPABASE_URL"),
                os.environ.get("SUPABASE_KEY")
            )
            supabase_authed.auth.set_session(access_token, refresh_token=None)

            # Build profile
            default_profile = {
                'user_id': user_id,
                'full_name': email.split('@')[0],
                'company': '',
                'role': '',
                'phone': '',
                'linkedin': '',
                'created_at': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            }

            # Insert profile
            insert_response = supabase_authed.table('user_profiles').insert(default_profile).execute()
            if insert_response.data:
                print("✅ Profile created successfully.")
                return True
            else:
                st.error("Signup succeeded, but profile creation failed.")
                return False
        else:
            st.error("Signup failed: No user returned.")
            return False

    except Exception as e:
        st.error(f"Signup failed: {str(e)}")
        print("❌ Signup exception:", e)
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
                st.switch_page("pages/login.py")
        else:
            st.switch_page("pages/home.py")
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
    
    # Add signup link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.switch_page("pages/signup.py")

    # Login link
    st.markdown("---")
    if st.button("Already have an account? Login here"):
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 