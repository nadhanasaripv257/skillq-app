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
    if 'user_profile' not in st.session_state:
        st.session_state.user_profile = {}

def load_user_profile():
    """Load user profile from Supabase"""
    try:
        response = supabase.table('profiles').select('*').eq('email', st.session_state.user_email).execute()
        if response.data:
            st.session_state.user_profile = response.data[0]
        else:
            # Create default profile if none exists
            st.session_state.user_profile = {
                'email': st.session_state.user_email,
                'full_name': '',
                'company': '',
                'role': '',
                'phone': '',
                'linkedin': ''
            }
    except Exception as e:
        st.error(f"Error loading profile: {str(e)}")

def save_user_profile(profile_data):
    """Save user profile to Supabase"""
    try:
        # Check if profile exists
        response = supabase.table('profiles').select('*').eq('email', st.session_state.user_email).execute()
        
        if response.data:
            # Update existing profile
            supabase.table('profiles').update(profile_data).eq('email', st.session_state.user_email).execute()
        else:
            # Create new profile
            profile_data['email'] = st.session_state.user_email
            supabase.table('profiles').insert(profile_data).execute()
        
        st.success("Profile updated successfully!")
        return True
    except Exception as e:
        st.error(f"Error saving profile: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="SkillQ - Profile Settings",
        page_icon="👤",
        layout="centered"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

    # Load user profile
    load_user_profile()

    st.title("👤 Profile Settings")
    
    with st.form("profile_form"):
        full_name = st.text_input(
            "Full Name",
            value=st.session_state.user_profile.get('full_name', ''),
            placeholder="Enter your full name"
        )
        
        company = st.text_input(
            "Company",
            value=st.session_state.user_profile.get('company', ''),
            placeholder="Enter your company name"
        )
        
        role = st.text_input(
            "Role",
            value=st.session_state.user_profile.get('role', ''),
            placeholder="Enter your role"
        )
        
        phone = st.text_input(
            "Phone",
            value=st.session_state.user_profile.get('phone', ''),
            placeholder="Enter your phone number"
        )
        
        linkedin = st.text_input(
            "LinkedIn Profile",
            value=st.session_state.user_profile.get('linkedin', ''),
            placeholder="Enter your LinkedIn profile URL"
        )
        
        submit = st.form_submit_button("Update Profile")
        
        if submit:
            profile_data = {
                'full_name': full_name,
                'company': company,
                'role': role,
                'phone': phone,
                'linkedin': linkedin
            }
            if save_user_profile(profile_data):
                st.session_state.user_profile.update(profile_data)

    # Add navigation buttons at the bottom
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🏠 Back to Home"):
            st.switch_page("pages/home.py")
    
    with col2:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_email = None
            st.session_state.user_profile = {}
            st.switch_page("login.py")

if __name__ == "__main__":
    main() 