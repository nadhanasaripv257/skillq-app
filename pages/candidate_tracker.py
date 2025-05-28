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
    if 'tracker_page' not in st.session_state:
        st.session_state.tracker_page = 1
    if 'tracker_per_page' not in st.session_state:
        st.session_state.tracker_per_page = 5
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = time.time()

@st.cache_data(ttl=300, show_spinner=False)
def get_contacted_candidates(recruiter_id, refresh_key=None, filter_date=None):
    """Get all contacted candidates with optional date filter"""
    try:
        # Base query
        query = supabase.table('recruiter_notes')\
            .select('*, resumes!inner(full_name, current_or_last_job_title, location, email, phone, linkedin_url)')\
            .eq('recruiter_id', recruiter_id)\
            .eq('contact_status', True)
        
        # Add date filter if provided
        if filter_date:
            # Convert date to ISO format string
            date_str = filter_date.isoformat()
            query = query.eq('follow_up_date', date_str)
        
        # Execute query
        response = query.order('follow_up_date', desc=True)\
            .execute()
            
        if not response.data:
            return []
            
        return response.data
    except Exception as e:
        st.error(f"Error fetching candidates: {str(e)}")
        return []

def format_timestamp(timestamp):
    """Format timestamp to readable string"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return timestamp

def main():
    st.set_page_config(
        page_title="SkillQ - Candidate Tracker",
        page_icon="👥",
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
        st.error("Please log in to view candidate tracker")
        if st.button("Go to Login"):
            st.switch_page("pages/login.py")
        return
    
    recruiter_id = user_response.user.id

    # Add back button at the top
    if st.button("← Back to Home"):
        st.switch_page("pages/home.py")

    # Header
    st.title("👥 Candidate Tracker")
    st.write("Track your contacted candidates and follow-ups")

    # Add refresh button
    if st.button("🔄 Refresh"):
        st.session_state.refresh_key = time.time()
        st.rerun()

    # Add view options
    st.subheader("📅 View Options")
    view_option = st.radio(
        "Select View",
        ["All Candidates", "Filter by Follow-up Date"],
        horizontal=True,
        help="Choose whether to view all candidates or filter by follow-up date"
    )

    # Add date filter if selected
    filter_date = None
    if view_option == "Filter by Follow-up Date":
        col1, col2 = st.columns([1, 2])
        with col1:
            filter_date = st.date_input(
                "Select Date",
                value=None,
                help="Filter candidates by their follow-up date"
            )
        with col2:
            if st.button("Clear Filter"):
                filter_date = None
                st.rerun()

    # Get contacted candidates with date filter
    candidates = get_contacted_candidates(
        recruiter_id,
        st.session_state.refresh_key,
        filter_date
    )

    if not candidates:
        if view_option == "Filter by Follow-up Date" and filter_date:
            st.info(f"No candidates found with follow-up date on {filter_date.strftime('%Y-%m-%d')}")
        else:
            st.info("No contacted candidates found. Start by contacting candidates from your drafts.")
        return

    # Create a table of candidates
    st.subheader("📋 Contacted Candidates Overview")
    
    # Prepare data for the table
    table_data = []
    for candidate in candidates:
        resume = candidate['resumes']
        # Create a unique anchor ID for each candidate
        anchor_id = resume['full_name'].lower().replace(' ', '-')
        
        # Handle follow-up date
        follow_up_date = None
        if candidate.get('follow_up_date'):
            try:
                # Parse the ISO format date from Supabase
                follow_up_date = pd.to_datetime(candidate['follow_up_date']).date()
            except (ValueError, TypeError) as e:
                st.error(f"Error parsing follow-up date for {resume['full_name']}: {str(e)}")
                follow_up_date = None
            
        table_data.append({
            'Candidate Name': resume['full_name'],
            'View Details': f"[View Details](#{anchor_id})",
            'Current Role': resume['current_or_last_job_title'],
            'Location': resume['location'],
            'Email': resume.get('email', 'N/A'),
            'Phone': resume.get('phone', 'N/A'),
            'LinkedIn': resume.get('linkedin_url', 'N/A'),
            'Follow-up Required': candidate.get('follow_up_required', False),
            'Follow-up Date': follow_up_date,
            'Last Contact': format_timestamp(candidate.get('updated_at', candidate['created_at']))
        })
    
    # Create DataFrame
    df = pd.DataFrame(table_data)
    
    # Display the dataframe with editable columns
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Candidate Name": st.column_config.TextColumn(
                "Candidate Name",
                help="Candidate's full name",
                disabled=True
            ),
            "View Details": st.column_config.TextColumn(
                "View Details",
                help="Click to view candidate details",
                disabled=True
            ),
            "Follow-up Required": st.column_config.CheckboxColumn(
                "Follow-up Required",
                help="Check if follow-up is required",
                default=False,
                required=True
            ),
            "Follow-up Date": st.column_config.DateColumn(
                "Follow-up Date",
                help="Date when follow-up should be done",
                format="YYYY-MM-DD",
                step=1
            )
        },
        disabled=["Candidate Name", "View Details", "Current Role", "Location", "Email", "Phone", "LinkedIn", "Last Contact"]
    )

    # Save changes to follow-up status
    if st.button("💾 Save Follow-up Changes"):
        try:
            # Get the current state of the dataframe
            updated_df = edited_df
            
            # Update each candidate's follow-up status
            for i, row in updated_df.iterrows():
                try:
                    # Convert the date to ISO format with timezone
                    if pd.notna(row['Follow-up Date']):
                        follow_up_date = row['Follow-up Date'].strftime('%Y-%m-%dT00:00:00Z')
                    else:
                        follow_up_date = None
                except (AttributeError, ValueError) as e:
                    st.error(f"Error processing date: {str(e)}")
                    follow_up_date = None
                    
                data = {
                    'follow_up_required': bool(row['Follow-up Required']),
                    'follow_up_date': follow_up_date,
                    'updated_at': datetime.now(UTC).isoformat()
                }
                
                # Debug: Show the data being sent to Supabase
                st.write(f"Updating candidate {i+1} with data:", data)
                
                response = supabase.table('recruiter_notes')\
                    .update(data)\
                    .eq('id', candidates[i]['id'])\
                    .execute()
                
                if hasattr(response, 'error') and response.error:
                    st.error(f"Error updating follow-up status: {response.error}")
                    return
                else:
                    st.write(f"Successfully updated candidate {i+1}")
            
            st.success("Follow-up status changes saved successfully!")
            st.session_state.refresh_key = time.time()
            st.rerun()
            
        except Exception as e:
            st.error(f"Error updating follow-up status: {str(e)}")
            st.error("Please try again or contact support if the issue persists.")

    # Display detailed view for each candidate
    st.subheader("📝 Candidate Details")
    for candidate in candidates:
        resume = candidate['resumes']
        with st.expander(f"👤 {resume['full_name']} - {resume['current_or_last_job_title']}", expanded=True):
            # Candidate summary
            st.markdown("#### Candidate Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Name:** {resume['full_name']}")
                st.markdown(f"**Current Role:** {resume['current_or_last_job_title']}")
                st.markdown(f"**Location:** {resume['location']}")
            with col2:
                st.markdown(f"**Email:** {resume.get('email', 'N/A')}")
                st.markdown(f"**Phone:** {resume.get('phone', 'N/A')}")
                if resume.get('linkedin_url'):
                    st.markdown(f"**LinkedIn:** [{resume['linkedin_url']}]({resume['linkedin_url']})")
            
            # Last outreach message
            st.markdown("#### Last Outreach Message")
            st.text_area(
                "Message:",
                value=candidate['outreach_message'],
                height=150,
                disabled=True
            )
            
            # Follow-up status
            st.markdown("#### Follow-up Status")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Follow-up Required:** {'Yes' if candidate.get('follow_up_required') else 'No'}")
            with col2:
                follow_up_date = candidate.get('follow_up_date')
                if follow_up_date:
                    st.markdown(f"**Follow-up Date:** {format_timestamp(follow_up_date)}")
            
            # Update follow-up status
            with st.form(key=f"update_followup_{candidate['id']}"):
                st.markdown("#### Update Follow-up Status")
                new_follow_up_required = st.checkbox("Follow-up Required", value=candidate.get('follow_up_required', False))
                new_follow_up_date = st.date_input(
                    "Follow-up Date",
                    value=pd.to_datetime(candidate.get('follow_up_date')).date() if candidate.get('follow_up_date') else None
                )
                
                if st.form_submit_button("Update Follow-up Status"):
                    try:
                        data = {
                            'follow_up_required': new_follow_up_required,
                            'follow_up_date': new_follow_up_date.strftime('%Y-%m-%dT00:00:00Z') if new_follow_up_date else None,
                            'updated_at': datetime.now(UTC).isoformat()
                        }
                        
                        response = supabase.table('recruiter_notes')\
                            .update(data)\
                            .eq('id', candidate['id'])\
                            .execute()
                        
                        if hasattr(response, 'error') and response.error:
                            st.error(f"Error updating follow-up status: {response.error}")
                        else:
                            st.success("Follow-up status updated successfully!")
                            st.session_state.refresh_key = time.time()
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"Error updating follow-up status: {str(e)}")
            
            # Timestamps
            st.markdown(f"*First Contact: {format_timestamp(candidate['created_at'])}*")
            if candidate.get('updated_at'):
                st.markdown(f"*Last Updated: {format_timestamp(candidate['updated_at'])}*")

if __name__ == "__main__":
    main() 