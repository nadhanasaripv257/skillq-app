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
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

def main():
    st.set_page_config(
        page_title="SkillQ - Login",
        page_icon="🔐",
        layout="centered"
    )
    
    initialize_session_state()
    
    # If already authenticated, redirect to home
    if st.session_state.authenticated:
        st.switch_page("pages/home.py")
        return

    st.title("🔐 Login to SkillQ")
    
    # Create a form for login
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        
        if submit:
            try:
                # Attempt to sign in with Supabase
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if response.user:
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.session_state.user_id = response.user.id
                    st.success("Login successful!")
                    st.switch_page("pages/home.py")
                else:
                    st.error("Invalid email or password")
            except Exception as e:
                st.error(f"Login failed: {str(e)}")
    
    # Add signup link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.switch_page("pages/signup.py")

if __name__ == "__main__":
    main() 