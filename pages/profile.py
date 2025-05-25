import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime

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

def get_user_profile(user_email):
    """Get user profile from Supabase"""
    try:
        # First get the user's ID from auth.users
        user_response = supabase.auth.get_user()
        if not user_response.user:
            return None
        
        user_id = user_response.user.id
        
        # Then get the profile data
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            return profile_response.data[0]
        return None
    except Exception as e:
        st.error(f"Error fetching profile: {str(e)}")
        return None

def save_user_profile(user_email, profile_data):
    """Save user profile to Supabase"""
    try:
        # Get the user's ID from auth.users
        user_response = supabase.auth.get_user()
        if not user_response.user:
            return False
        
        user_id = user_response.user.id
        
        # Check if profile exists
        existing_profile = get_user_profile(user_email)
        
        if existing_profile:
            # Update existing profile
            response = supabase.table('user_profiles').update({
                'full_name': profile_data['full_name'],
                'company': profile_data['company'],
                'role': profile_data['role'],
                'phone': profile_data['phone'],
                'linkedin': profile_data['linkedin'],
                'updated_at': datetime.utcnow().isoformat()
            }).eq('user_id', user_id).execute()
        else:
            # Create new profile
            profile_data['user_id'] = user_id
            response = supabase.table('user_profiles').insert(profile_data).execute()
        
        return True
    except Exception as e:
        st.error(f"Error saving profile: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="SkillQ - Profile Settings",
        page_icon="👤",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

    # Add back button at the top
    if st.button("← Back to Home"):
        st.switch_page("pages/home.py")

    st.title("👤 Profile Settings")
    st.write(f"Welcome, {st.session_state.user_email}!")

    # Get existing profile data
    profile_data = get_user_profile(st.session_state.user_email)
    
    # Create form for profile data
    with st.form("profile_form"):
        st.subheader("Update Your Profile")
        
        # Initialize form fields with existing data or empty strings
        full_name = st.text_input("Full Name", value=profile_data.get('full_name', '') if profile_data else '')
        company = st.text_input("Company", value=profile_data.get('company', '') if profile_data else '')
        role = st.text_input("Role", value=profile_data.get('role', '') if profile_data else '')
        phone = st.text_input("Phone", value=profile_data.get('phone', '') if profile_data else '')
        linkedin = st.text_input("LinkedIn Profile", value=profile_data.get('linkedin', '') if profile_data else '')
        
        # Submit button
        submitted = st.form_submit_button("Save Profile")
        
        if submitted:
            # Prepare profile data
            profile_data = {
                'full_name': full_name,
                'company': company,
                'role': role,
                'phone': phone,
                'linkedin': linkedin
            }
            
            # Save profile data
            if save_user_profile(st.session_state.user_email, profile_data):
                st.success("Profile updated successfully!")
            else:
                st.error("Failed to update profile. Please try again.")

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 