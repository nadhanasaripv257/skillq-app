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

def create_user_profile(user_id: str, email: str) -> bool:
    """Create a user profile in Supabase if it doesn't exist"""
    try:
        # Check if profile already exists
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            # Profile exists, just return success
            return True
        
        # Profile doesn't exist, create new one
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
        
        # Use upsert to handle potential race conditions
        insert_response = supabase.table('user_profiles').upsert(
            default_profile,
            on_conflict='user_id'  # This will update if user_id exists
        ).execute()
        
        return bool(insert_response.data)
        
    except Exception as e:
        st.error(f"Error managing user profile: {str(e)}")
        return False

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
                    # Create user profile
                    if create_user_profile(response.user.id, email):
                        st.session_state.authenticated = True
                        st.session_state.user_email = email
                        st.session_state.user_id = response.user.id
                        st.success("Login successful!")
                        st.switch_page("pages/home.py")
                    else:
                        st.error("Failed to create user profile. Please try again.")
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