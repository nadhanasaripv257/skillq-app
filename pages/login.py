import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, UTC

# Load environment variables
load_dotenv()

# Initialize base Supabase client (for login only)
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

def create_user_profile(user_id: str, email: str, access_token: str) -> bool:
    """Create a user profile in Supabase if it doesn't exist"""
    try:
        # Create authenticated client
        supabase_authed = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_KEY")
        )
        
        # Set the session with the access token and empty refresh token
        supabase_authed.auth.set_session(access_token, refresh_token="")
        
        # Check if profile exists
        profile_response = supabase_authed.table('user_profiles').select('*').eq('user_id', user_id).execute()
        if profile_response.data:
            print("✅ Profile already exists.")
            return True

        # Create default profile
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

        print("🔧 Attempting to insert profile with session auth...")
        insert_response = supabase_authed.table('user_profiles').insert(default_profile).execute()
        print("✅ Insert response:", insert_response)
        return bool(insert_response.data)

    except Exception as e:
        st.error(f"Error managing user profile: {str(e)}")
        print("❌ Full error details:\n", e)
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
                print(f"🔐 Attempting login for: {email}")
                
                # Attempt to sign in with Supabase
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if response.user:
                    print(f"✅ Login successful. User ID: {response.user.id}")
                    user_id = response.user.id
                    access_token = response.session.access_token

                    # Set session state before profile creation
                    st.session_state.authenticated = True
                    st.session_state.user_email = email
                    st.session_state.user_id = user_id

                    if create_user_profile(user_id, email, access_token):
                        st.success("Login successful!")
                        st.switch_page("pages/home.py")
                    else:
                        print("❌ Failed to create profile")
                        st.error("Failed to create user profile. Please try again.")
                        # Reset session state on failure
                        st.session_state.authenticated = False
                        st.session_state.user_email = None
                        st.session_state.user_id = None
                else:
                    print("❌ Login failed: Invalid credentials")
                    st.error("Invalid email or password")
            except Exception as e:
                print(f"🔥 Login exception: {e}")
                st.error(f"Login failed: {str(e)}")
    
    # Add signup link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.switch_page("pages/signup.py")

if __name__ == "__main__":
    main() 