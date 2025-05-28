import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, UTC
import pandas as pd
import time

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
    if 'drafts_page' not in st.session_state:
        st.session_state.drafts_page = 1
    if 'drafts_per_page' not in st.session_state:
        st.session_state.drafts_per_page = 5
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = time.time()

@st.cache_data(ttl=300, show_spinner=False)
def get_recruiter_drafts(recruiter_id, page=1, per_page=5, refresh_key=None):
    """Get recruiter drafts with pagination"""
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get drafts with candidate info including contact details
        response = supabase.table('recruiter_notes')\
            .select('*, resumes!inner(full_name, current_or_last_job_title, location, email, phone, linkedin_url)')\
            .eq('recruiter_id', recruiter_id)\
            .order('created_at', desc=True)\
            .range(offset, offset + per_page - 1)\
            .execute()
            
        if not response.data:
            return [], 0
            
        # Get total count for pagination
        count_response = supabase.table('recruiter_notes')\
            .select('id', count='exact')\
            .eq('recruiter_id', recruiter_id)\
            .execute()
            
        total_count = count_response.count if count_response.count is not None else 0
        
        return response.data, total_count
    except Exception as e:
        st.error(f"Error fetching drafts: {str(e)}")
        return [], 0

def format_timestamp(timestamp):
    """Format timestamp to readable string"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return timestamp

def copy_to_clipboard(text):
    """Copy text to clipboard using JavaScript"""
    js = f"""
    <script>
        function copyToClipboard() {{
            const text = `{text}`;
            navigator.clipboard.writeText(text);
        }}
        copyToClipboard();
    </script>
    """
    st.components.v1.html(js, height=0)

def get_user_profile(refresh_key=None):
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
        page_title="SkillQ - My Drafts",
        page_icon="📁",
        layout="wide"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        return

    # Get user ID and profile
    user_response = supabase.auth.get_user()
    if not user_response.user:
        st.error("Please log in to view your drafts")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        return
    
    recruiter_id = user_response.user.id
    profile = get_user_profile(st.session_state.get("refresh_key"))
    
    if not profile:
        st.error("Error loading profile. Please try logging in again.")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        return

    # Add back button at the top
    if st.button("← Back to Home"):
        st.switch_page("pages/home.py")

    # Header
    st.title("📁 My Drafts")
    st.write("View and manage your saved outreach messages and screening questions")

    # Add refresh button
    if st.button("🔄 Refresh"):
        st.session_state.refresh_key = time.time()
        st.rerun()

    # Get drafts with pagination
    drafts, total_count = get_recruiter_drafts(
        recruiter_id,
        st.session_state.drafts_page,
        st.session_state.drafts_per_page,
        st.session_state.refresh_key
    )

    if not drafts:
        st.info("No drafts found. Start by generating outreach messages for candidates.")
        return

    # Create a table of drafts
    st.subheader("📋 Drafts Overview")
    
    # Prepare data for the table
    table_data = []
    for draft in drafts:
        candidate = draft['resumes']
        # Create a unique anchor ID for each candidate
        anchor_id = f"candidate_{draft['id']}"
        table_data.append({
            'Candidate Name': candidate["full_name"],
            'View Details': f"#{anchor_id}",
            'Current Role': candidate['current_or_last_job_title'],
            'Location': candidate['location'],
            'Email': candidate.get('email', 'N/A'),
            'Phone': candidate.get('phone', 'N/A'),
            'LinkedIn': candidate.get('linkedin_url', 'N/A'),
            'Created': format_timestamp(draft['created_at']),
            'Last Updated': format_timestamp(draft.get('updated_at', draft['created_at']))
        })
    
    # Display the table with HTML formatting enabled
    df = pd.DataFrame(table_data)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Candidate Name": st.column_config.TextColumn(
                "Candidate Name",
                help="Candidate's full name"
            ),
            "View Details": st.column_config.LinkColumn(
                "View Details",
                help="Click to view candidate details",
                display_text="View Details"
            )
        }
    )

    # Display detailed view for each draft
    st.subheader("📝 Draft Details")
    for draft in drafts:
        # Add an anchor for scrolling
        st.markdown(f'<div id="candidate_{draft["id"]}"></div>', unsafe_allow_html=True)
        with st.expander(f"📝 {draft['resumes']['full_name']} - {draft['resumes']['current_or_last_job_title']}", expanded=True):
            # Candidate summary
            st.markdown("#### Candidate Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Name:** {draft['resumes']['full_name']}")
                st.markdown(f"**Current Role:** {draft['resumes']['current_or_last_job_title']}")
                st.markdown(f"**Location:** {draft['resumes']['location']}")
            with col2:
                st.markdown(f"**Email:** {draft['resumes'].get('email', 'N/A')}")
                st.markdown(f"**Phone:** {draft['resumes'].get('phone', 'N/A')}")
                if draft['resumes'].get('linkedin_url'):
                    st.markdown(f"**LinkedIn:** [{draft['resumes']['linkedin_url']}]({draft['resumes']['linkedin_url']})")
            
            # Outreach message
            st.markdown("#### Outreach Message")
            
            # Add recruiter info to the message
            recruiter_name = profile.get('full_name', '').split()[0] if profile.get('full_name') else ''
            company_name = profile.get('company_name', '')
            
            # Create a template with recruiter info
            message_template = draft['outreach_message']
            if recruiter_name:
                message_template = message_template.replace("[Your Name]", recruiter_name)
            if company_name:
                message_template = message_template.replace("[Your Company]", company_name)
            
            outreach_message = st.text_area(
                "Edit the message if needed:",
                value=message_template,
                height=150,
                key=f"outreach_{draft['id']}"
            )
            
            # Screening questions
            st.markdown("#### Screening Questions")
            questions = []
            for i, question in enumerate(draft['screening_questions'], 1):
                edited_question = st.text_input(
                    f"Question {i}:",
                    value=question,
                    key=f"question_{draft['id']}_{i}"
                )
                questions.append(edited_question)
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📋 Copy Message", key=f"copy_msg_{draft['id']}"):
                    copy_to_clipboard(outreach_message)
                    st.success("Message copied to clipboard!")
            
            with col2:
                if st.button("📋 Copy Questions", key=f"copy_q_{draft['id']}"):
                    questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
                    copy_to_clipboard(questions_text)
                    st.success("Questions copied to clipboard!")
            
            with col3:
                if st.button("💾 Save Changes", key=f"save_{draft['id']}"):
                    try:
                        # Update the draft
                        data = {
                            'outreach_message': outreach_message,
                            'screening_questions': questions,
                            'updated_at': datetime.now(UTC).isoformat()
                        }
                        
                        response = supabase.table('recruiter_notes')\
                            .update(data)\
                            .eq('id', draft['id'])\
                            .execute()
                        
                        if hasattr(response, 'error') and response.error:
                            st.error(f"Error saving changes: {response.error}")
                        else:
                            st.success("Changes saved successfully!")
                            # Force refresh
                            st.session_state.refresh_key = time.time()
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error saving changes: {str(e)}")
            
            # Timestamp
            st.markdown(f"*Created: {format_timestamp(draft['created_at'])}*")
            if draft.get('updated_at'):
                st.markdown(f"*Last updated: {format_timestamp(draft['updated_at'])}*")

    # Pagination
    total_pages = (total_count + st.session_state.drafts_per_page - 1) // st.session_state.drafts_per_page
    
    if total_pages > 1:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if st.session_state.drafts_page > 1:
                if st.button("← Previous"):
                    st.session_state.drafts_page -= 1
                    st.rerun()
        
        with col2:
            st.markdown(f"**Page {st.session_state.drafts_page} of {total_pages}**")
        
        with col3:
            if st.session_state.drafts_page < total_pages:
                if st.button("Next →"):
                    st.session_state.drafts_page += 1
                    st.rerun()

if __name__ == "__main__":
    main() 