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
        # Debug logging
        st.write("Debug - Creating profile with:")
        st.write("user_id:", user_id)
        
        # Verify session state
        try:
            session = supabase.auth.get_session()
            st.write("Debug - Current session:", session)
            if session:
                st.write("Debug - Session user ID:", session.user.id)
                st.write("Debug - Session access token exists:", bool(session.access_token))
        except Exception as session_error:
            st.write("Debug - Session check failed:", str(session_error))
        
        # Call debug_auth_uid() to verify the authenticated user ID
        try:
            uid_result = supabase.rpc("debug_auth_uid").execute()
            st.write("Debug - auth.uid() on backend:", uid_result.data)
            if uid_result.data is None:
                st.error("Warning: auth.uid() returned None - session may be broken or using service role key")
        except Exception as uid_error:
            st.write("Debug - debug_auth_uid() call failed:", str(uid_error))
        
        # Check if profile already exists
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            # Profile exists, just return success
            st.write("Debug - Profile already exists")
            return True
        
        # Profile doesn't exist, create new one
        default_profile = {
            'user_id': user_id,  # This must exactly match auth.uid()
            'full_name': email.split('@')[0],
            'company': '',
            'role': '',
            'phone': '',
            'linkedin': '',
            'created_at': datetime.now(UTC).isoformat(),
            'updated_at': datetime.now(UTC).isoformat()
        }
        
        st.write("Debug - Attempting to create profile with:", default_profile)
        
        # Insert new profile
        insert_response = supabase.table('user_profiles').insert(default_profile).execute()
        
        if insert_response.data:
            st.write("Debug - Profile created successfully")
        else:
            st.write("Debug - Profile creation failed:", insert_response.error)
        
        return bool(insert_response.data)
        
    except Exception as e:
        # If the error is due to duplicate key, that's fine - profile exists
        if hasattr(e, 'code') and e.code == '23505':  # PostgreSQL unique violation error code
            st.write("Debug - Profile already exists (caught by exception)")
            return True
        st.error(f"Error managing user profile: {str(e)}")
        st.write("Debug - Full error details:", e)
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
                    # Debug logging
                    st.write("Debug - Login successful")
                    st.write("Debug - User ID from response:", response.user.id)
                    
                    # Verify session immediately after login
                    try:
                        session = supabase.auth.get_session()
                        st.write("Debug - Session after login:", session)
                        if session:
                            st.write("Debug - Session user ID:", session.user.id)
                            st.write("Debug - Session access token exists:", bool(session.access_token))
                            
                            # Call debug_auth_uid() immediately after login
                            uid_result = supabase.rpc("debug_auth_uid").execute()
                            st.write("Debug - auth.uid() after login:", uid_result.data)
                            if uid_result.data is None:
                                st.error("Warning: auth.uid() returned None after login - session may be broken")
                    except Exception as session_error:
                        st.write("Debug - Session check failed:", str(session_error))
                    
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
                st.write("Debug - Full error details:", e)
    
    # Add signup link
    st.markdown("---")
    st.write("Don't have an account?")
    if st.button("Sign Up"):
        st.switch_page("pages/signup.py")

if __name__ == "__main__":
    main() 