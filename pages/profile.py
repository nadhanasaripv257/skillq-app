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
    if 'profile_updated' not in st.session_state:
        st.session_state.profile_updated = False

def get_user_profile():
    """Get user profile from Supabase with error handling"""
    try:
        # First check if we have a user_id in session state
        if not st.session_state.get('user_id'):
            print("❌ No user_id in session state")
            return None

        # Create service role client with explicit headers
        supabase_admin = create_client(
            supabase_url=os.environ.get("SUPABASE_URL"),
            supabase_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
            options={
                "headers": {
                    "apikey": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
                    "Authorization": f"Bearer {os.environ.get('SUPABASE_SERVICE_ROLE_KEY')}"
                }
            }
        )

        # Get the profile data using the session state user_id
        profile_response = supabase_admin.table('user_profiles').select('*').eq('user_id', st.session_state.user_id).execute()
        
        if profile_response.data:
            return profile_response.data[0]
        
        # If no profile exists, create a default one
        default_profile = {
            'user_id': st.session_state.user_id,
            'full_name': st.session_state.user_email.split('@')[0],
            'company': '',
            'role': '',
            'phone': '',
            'linkedin': '',
            'created_at': datetime.now(UTC).isoformat(),
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        # Insert the default profile using service role client
        insert_response = supabase_admin.table('user_profiles').insert(default_profile).execute()
        
        if insert_response.data:
            return insert_response.data[0]
        else:
            st.error("Failed to create default profile")
            return None
            
    except Exception as e:
        st.error(f"Error fetching profile: {str(e)}")
        print(f"❌ Profile error: {str(e)}")
        return None

def update_user_profile(profile_data):
    """Update user profile in Supabase with error handling"""
    try:
        # Get the user's ID from session state
        if not st.session_state.get('user_id'):
            st.error("No user ID found in session")
            return False
        
        user_id = st.session_state.user_id
        
        # Create service role client with explicit headers
        supabase_admin = create_client(
            supabase_url=os.environ.get("SUPABASE_URL"),
            supabase_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
            options={
                "headers": {
                    "apikey": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
                    "Authorization": f"Bearer {os.environ.get('SUPABASE_SERVICE_ROLE_KEY')}"
                }
            }
        )
        
        # Update the profile using service role client
        update_response = supabase_admin.table('user_profiles').update(profile_data).eq('user_id', user_id).execute()
        
        if update_response.data:
            st.session_state.profile_updated = True
            return True
        else:
            st.error("Failed to update profile")
            return False
            
    except Exception as e:
        st.error(f"Error updating profile: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="SkillQ - Profile",
        page_icon="👤",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.get('authenticated', False):
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        return

    # Add back button at the top
    if st.button("← Back to Home"):
        st.session_state.page = "Home"
        st.switch_page("pages/home.py")

    st.title("👤 Profile Settings")
    st.write(f"Welcome, {st.session_state.get('user_email', 'User')}!")

    # Get user profile
    profile = get_user_profile()
    
    if not profile:
        st.error("Error loading profile. Please try logging in again.")
        if st.button("Go to Login"):
            st.session_state.page = "Login"
            st.switch_page("pages/login.py")
        return

    # Create form for profile update
    with st.form("profile_form"):
        full_name = st.text_input("Full Name", value=profile.get('full_name', ''))
        company = st.text_input("Company", value=profile.get('company', ''))
        role = st.text_input("Role", value=profile.get('role', ''))
        phone = st.text_input("Phone", value=profile.get('phone', ''))
        linkedin = st.text_input("LinkedIn Profile", value=profile.get('linkedin', ''))
        
        submitted = st.form_submit_button("Update Profile")
        
        if submitted:
            profile_data = {
                'full_name': full_name,
                'company': company,
                'role': role,
                'phone': phone,
                'linkedin': linkedin,
                'updated_at': datetime.now(UTC).isoformat()
            }
            
            if update_user_profile(profile_data):
                st.success("Profile updated successfully!")
                st.rerun()

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 