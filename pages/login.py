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
        print(f"🔍 Creating profile for user: {user_id}")
        
        # Create authenticated client with session token
        supabase_authed: Client = create_client(
            os.environ.get("SUPABASE_URL"),
            os.environ.get("SUPABASE_KEY"),
            options={"global": {"headers": {"Authorization": f"Bearer {access_token}"}}}
        )
        
        # Verify session state
        try:
            session = supabase_authed.auth.get_session()
            print(f"📝 Current session: {session}")
            if session:
                print(f"👤 Session user ID: {session.user.id}")
                print(f"🔑 Session access token exists: {bool(session.access_token)}")
        except Exception as session_error:
            print(f"⚠️ Session check failed: {str(session_error)}")
        
        # Call debug_auth_uid() to verify the authenticated user ID
        try:
            uid_result = supabase_authed.rpc("debug_auth_uid").execute()
            print(f"🔐 auth.uid() on backend: {uid_result.data}")
            if uid_result.data is None:
                print("⚠️ Warning: auth.uid() returned None - session may be broken or using service role key")
        except Exception as uid_error:
            print(f"⚠️ debug_auth_uid() call failed: {str(uid_error)}")
        
        # Check if profile already exists
        profile_response = supabase_authed.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            print(f"✅ Profile already exists for user: {user_id}")
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
        
        print(f"📝 Attempting to create profile: {default_profile}")
        
        # Insert new profile using authenticated client
        insert_response = supabase_authed.table('user_profiles').insert(default_profile).execute()
        
        if insert_response.data:
            print(f"✅ Profile created successfully for user: {user_id}")
        else:
            print(f"❌ Profile creation failed: {insert_response.error}")
        
        return bool(insert_response.data)
        
    except Exception as e:
        # If the error is due to duplicate key, that's fine - profile exists
        if hasattr(e, 'code') and e.code == '23505':  # PostgreSQL unique violation error code
            print(f"ℹ️ Profile already exists (caught by exception) for user: {user_id}")
            return True
        print(f"🔥 Error managing user profile: {str(e)}")
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
                print(f"🔐 Attempting login for: {email}")
                
                # Attempt to sign in with Supabase
                response = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                
                if response.user:
                    print(f"✅ Login successful. User ID: {response.user.id}")
                    
                    # Create authenticated client with session token
                    session = response.session
                    supabase_authed: Client = create_client(
                        os.environ.get("SUPABASE_URL"),
                        os.environ.get("SUPABASE_KEY"),
                        options={"global": {"headers": {"Authorization": f"Bearer {session.access_token}"}}}
                    )
                    
                    # Verify session immediately after login
                    try:
                        session = supabase_authed.auth.get_session()
                        print(f"📝 Session after login: {session}")
                        if session:
                            print(f"👤 Session user ID: {session.user.id}")
                            print(f"🔑 Session access token exists: {bool(session.access_token)}")
                            
                            # Call debug_auth_uid() immediately after login
                            uid_result = supabase_authed.rpc("debug_auth_uid").execute()
                            print(f"🔐 auth.uid() after login: {uid_result.data}")
                            if uid_result.data is None:
                                print("⚠️ Warning: auth.uid() returned None after login - session may be broken")
                    except Exception as session_error:
                        print(f"⚠️ Session check failed: {str(session_error)}")
                    
                    # Create user profile with authenticated client
                    if create_user_profile(response.user.id, email, session.access_token):
                        print("✅ Profile check/creation successful")
                        st.session_state.authenticated = True
                        st.session_state.user_email = email
                        st.session_state.user_id = response.user.id
                        st.success("Login successful!")
                        st.switch_page("pages/home.py")
                    else:
                        print("❌ Failed to create profile")
                        st.error("Failed to create user profile. Please try again.")
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