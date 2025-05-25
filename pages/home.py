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

def get_user_profile():
    """Get user profile from Supabase"""
    try:
        # Get the user's ID from auth.users
        user_response = supabase.auth.get_user()
        if not user_response.user:
            return None
        
        user_id = user_response.user.id
        
        # Get the profile data
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            return profile_response.data[0]
        return None
    except Exception as e:
        st.error(f"Error fetching profile: {str(e)}")
        return None

def main():
    st.set_page_config(
        page_title="SkillQ - Home",
        page_icon="🏠",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

    # Get user profile
    profile = get_user_profile()
    display_name = profile.get('full_name', '') if profile else st.session_state.user_email

    st.title("🏠 Welcome to SkillQ")
    st.write(f"Hello, {display_name}!")

    # Create three columns for different sections
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📄 Resume Management")
        st.write("Upload and manage candidate resumes")
        if st.button("Go to Upload Page"):
            st.switch_page("pages/upload.py")

    with col2:
        st.subheader("💬 Ask SkillQ")
        st.write("Get insights about candidate skills")
        if st.button("Start Chat"):
            st.switch_page("pages/chat.py")

    with col3:
        st.subheader("👤 Profile Settings")
        st.write("Update your profile information")
        if st.button("Edit Profile"):
            st.switch_page("pages/profile.py")

    # Display profile information if available
    if profile:
        st.markdown("---")
        st.subheader("Your Profile Information")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Company:** {profile.get('company', 'Not specified')}")
            st.write(f"**Role:** {profile.get('role', 'Not specified')}")
        
        with col2:
            st.write(f"**Phone:** {profile.get('phone', 'Not specified')}")
            st.write(f"**LinkedIn:** {profile.get('linkedin', 'Not specified')}")

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 