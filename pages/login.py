import streamlit as st
from supabase import create_client, Client
from postgrest import PostgrestClient
import os
from dotenv import load_dotenv
from datetime import datetime, UTC
import logging

# Load environment variables
load_dotenv()

# Initialize base Supabase client (for login only)
supabase: Client = create_client(
    supabase_url=os.environ.get("SUPABASE_URL"),
    supabase_key=os.environ.get("SUPABASE_KEY")
)

logger = logging.getLogger(__name__)

def get_authed_supabase(access_token: str, refresh_token: str = None) -> Client:
    """Create an authenticated Supabase client using the access token"""
    try:
        # Create client with the token in the headers
        client = create_client(
            supabase_url=os.environ.get("SUPABASE_URL"),
            supabase_key=os.environ.get("SUPABASE_KEY")
        )
        
        # Set the session with both access token and refresh token
        client.auth.set_session(access_token, refresh_token or access_token)
        
        # Set the auth header for subsequent requests
        client.auth.headers = {
            "Authorization": f"Bearer {access_token}",  # critical for RLS
            "apikey": os.environ.get("SUPABASE_KEY")
        }
        
        # Test auth.uid() recognition
        try:
            test_response = client.table('user_profiles').select('auth.uid()').execute()
            print("🔍 Auth.uid() test response:", test_response)
        except Exception as e:
            print("⚠️ Auth.uid() test failed:", str(e))
        
        return client
    except Exception as e:
        logger.error(f"Error creating authenticated client: {str(e)}")
        raise

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

def create_user_profile(user_id: str, email: str, access_token: str, refresh_token: str = None) -> bool:
    """Create a user profile in Supabase if it doesn't exist"""
    try:
        print(f"🔧 Creating service role client for user: {user_id}")
        # Create service role client for profile creation
        supabase_admin = create_client(
            supabase_url=os.environ.get("SUPABASE_URL"),
            supabase_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY")  # Use service role key
        )
        
        # Debug prints for auth context
        print("🔑 Access Token (first 20 chars):", access_token[:20])
        if refresh_token:
            print("🔄 Refresh Token (first 20 chars):", refresh_token[:20])
        print("👤 user_id:", user_id)
        
        # Check if profile exists using service role client
        profile_response = supabase_admin.table('user_profiles').select('*').eq('user_id', user_id).execute()
        print("🔍 Profile check response:", profile_response)
        
        if profile_response and hasattr(profile_response, 'data') and profile_response.data:
            print("✅ Profile already exists.")
            return True

        # Create default profile using service role client
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

        print("🔧 Attempting to insert profile with service role...")
        insert_response = supabase_admin.table('user_profiles').insert(default_profile).execute()
        print("✅ Insert response:", insert_response)
        
        if insert_response and hasattr(insert_response, 'data') and insert_response.data:
            print("✅ Profile created successfully")
            return True
        else:
            print("❌ Profile creation failed - no data returned")
            return False

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
                
                # Debug logging
                print("🧪 Full login response:", response)
                print("🧪 Response type:", type(response))
                
                # Defensive null checking
                if response is None or response.user is None or response.session is None:
                    print("❌ Login failed: Incomplete response")
                    st.error("Invalid email or password")
                    return
                
                user_id = response.user.id
                access_token = response.session.access_token
                refresh_token = response.session.refresh_token
                
                print(f"✅ Login successful. User ID: {user_id}")
                
                # Set session state before profile creation
                st.session_state.authenticated = True
                st.session_state.user_email = email
                st.session_state.user_id = user_id

                if create_user_profile(user_id, email, access_token, refresh_token):
                    st.success("Login successful!")
                    st.switch_page("pages/home.py")
                else:
                    print("❌ Failed to create profile")
                    st.error("Failed to create user profile. Please try again.")
                    # Reset session state on failure
                    st.session_state.authenticated = False
                    st.session_state.user_email = None
                    st.session_state.user_id = None
                    
            except Exception as e:
                print(f"🔥 Login exception: {e}")
                st.error(f"Login failed: {str(e)}")
                # Reset session state on error
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.user_id = None
    
    # Add signup link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.switch_page("pages/signup.py")

if __name__ == "__main__":
    main() 