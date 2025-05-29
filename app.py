import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=os.getenv("SUPABASE_URL"),
    supabase_key=os.getenv("SUPABASE_KEY")
)

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None

def main():
    st.set_page_config(
        page_title="SkillQ - AI-Powered Talent Search",
        page_icon="🔍",
        layout="wide"
    )
    
    initialize_session_state()
    
    # If not authenticated, redirect to login
    if not st.session_state.authenticated:
        st.switch_page("pages/login.py")
        return

    st.title("🔍 Welcome to SkillQ")
    st.write(f"Hello, {st.session_state.user_email}!")
    
    # Main navigation
    st.subheader("Navigation")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📄 Upload Resumes"):
            st.switch_page("pages/upload.py")
    
    with col2:
        if st.button("💬 Chat with SkillQ"):
            st.switch_page("pages/chat.py")
    
    with col3:
        if st.button("👤 Profile"):
            st.switch_page("pages/profile.py")
    
    # Add logout button
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 