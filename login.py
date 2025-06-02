import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

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

def login_user(email: str, password: str) -> bool:
    """Attempt to login user with Supabase"""
    try:
        # Using the correct method for Supabase v1.2.0
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Check if we have a user in the response
        if hasattr(response, 'user') and response.user:
            st.session_state.authenticated = True
            st.session_state.user_email = email
            return True
        else:
            st.error("Invalid email or password")
            return False
    except Exception as e:
        st.error(f"Login failed: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="SkillQ - Login",
        page_icon="🔐",
        layout="centered"
    )
    
    initialize_session_state()
    
    # If user is already authenticated, redirect to home page
    if st.session_state.authenticated:
        st.switch_page("pages/home.py")
        return

    # Login form
    st.title("🔐 SkillQ Login")
    
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        submit = st.form_submit_button("Login")
        
        if submit:
            if not email or not password:
                st.error("Please fill in all fields")
            else:
                if login_user(email, password):
                    st.switch_page("pages/home.py")
    
    # Sign up link
    st.markdown("---")
    if st.button("Don't have an account? Sign up here"):
        st.switch_page("pages/signup.py")

if __name__ == "__main__":
    main() 