import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, UTC
import pandas as pd
import time
from slugify import slugify

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=os.environ.get("SUPABASE_URL"),
    supabase_key=os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
)

# Set the headers explicitly
supabase.postgrest.headers = {
    "apikey": os.environ.get("SUPABASE_SERVICE_ROLE_KEY"),
    "Authorization": f"Bearer {os.environ.get('SUPABASE_SERVICE_ROLE_KEY')}"
}

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
    if 'drafts_df' not in st.session_state:
        st.session_state.drafts_df = None
    if 'selected_draft' not in st.session_state:
        st.session_state.selected_draft = None

@st.cache_data(ttl=300, show_spinner=False)
def get_drafts(recruiter_id, page=1, per_page=5, refresh_key=None):
    """Get drafts with pagination"""
    try:
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get drafts with their details, joining with resumes_pii for PII data
        response = supabase.table('recruiter_notes')\
            .select('*, resumes!inner(current_or_last_job_title, location, resumes_pii!inner(full_name, email, phone))')\
            .eq('recruiter_id', recruiter_id)\
            .eq('contact_status', False)\
            .order('created_at', desc=True)\
            .range(offset, offset + per_page - 1)\
            .execute()
            
        if not response.data:
            return [], 0
            
        # Get total count for pagination
        count_response = supabase.table('recruiter_notes')\
            .select('id', count='exact')\
            .eq('recruiter_id', recruiter_id)\
            .eq('contact_status', False)\
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
        # Get user ID from session state
        if not st.session_state.get('user_id'):
            print("❌ No user_id in session state")
            return None
        
        user_id = st.session_state.user_id
        
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
        page_icon="📝",
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
        st.error("Please log in to view drafts")
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
    st.title("📝 My Drafts")
    st.write("Manage your candidate outreach drafts")

    # Add refresh button
    if st.button("🔄 Refresh"):
        st.session_state.refresh_key = time.time()
        st.session_state.selected_draft = None
        st.session_state.drafts_df = None  # Clear it so it can be recreated clean
        st.rerun()

    # Get drafts with pagination
    drafts, total_count = get_drafts(
        recruiter_id,
        st.session_state.drafts_page,
        st.session_state.drafts_per_page,
        st.session_state.refresh_key
    )

    if not drafts:
        st.info("No drafts found. Start by creating outreach messages for candidates.")
        return

    # Create a table of drafts
    st.subheader("📋 Drafts Overview")
    
    # Prepare data for the table
    table_data = []
    for draft in drafts:
        resume = draft['resumes']
        pii_data = resume['resumes_pii'][0] if resume.get('resumes_pii') and len(resume['resumes_pii']) > 0 else {}
        # Create a unique anchor ID for each draft
        full_name = str(pii_data.get('full_name', '') or '')
        anchor_id = slugify(full_name)
        try:
            follow_up_date = pd.to_datetime(draft.get('follow_up_date')).date() if draft.get('follow_up_date') else None
        except (ValueError, TypeError):
            follow_up_date = None
            
        table_data.append({
            'Select': False,  # Initialize as False
            'Candidate Name': pii_data.get('full_name', 'N/A'),
            'Current Role': resume.get('current_or_last_job_title', 'N/A'),
            'Location': resume.get('location', 'N/A'),
            'Email': pii_data.get('email', 'N/A'),
            'Phone': pii_data.get('phone', 'N/A'),
            'Contacted': draft.get('contact_status', False),
            'Follow-up Required': draft.get('follow_up_required', False),
            'Follow-up Date': follow_up_date,
            'Last Updated': format_timestamp(draft.get('updated_at', draft['created_at']))
        })
    
    # Create DataFrame
    df = pd.DataFrame(table_data)

    # Always reset Select column to False
    df["Select"] = False

    # Store the dataframe in session state
    st.session_state.drafts_df = df
    
    # Display the dataframe with editable columns
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select draft to view details",
                default=False,
                required=True
            ),
            "Candidate Name": st.column_config.TextColumn(
                "Candidate Name",
                help="Candidate's full name",
                disabled=True
            ),
            "Current Role": st.column_config.TextColumn(
                "Current Role",
                help="Candidate's current or last job title",
                disabled=True
            ),
            "Location": st.column_config.TextColumn(
                "Location",
                help="Candidate's location",
                disabled=True
            ),
            "Email": st.column_config.TextColumn(
                "Email",
                help="Candidate's email",
                disabled=True
            ),
            "Phone": st.column_config.TextColumn(
                "Phone",
                help="Candidate's phone",
                disabled=True
            ),
            "Contacted": st.column_config.CheckboxColumn(
                "Contacted",
                help="Check if you have contacted this candidate",
                default=False,
                required=True
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
        disabled=["Candidate Name", "Current Role", "Location", "Email", "Phone", "Last Updated"]
    )

    # Add view button below the table
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("👁 View Details", use_container_width=True):
            # Get the selected draft
            selected = edited_df[edited_df['Select'] == True]
            if len(selected) == 0:
                st.warning("Please select a draft to view details")
            elif len(selected) > 1:
                st.warning("Please select only one draft to view details")
            else:
                # Get the selected draft's name and convert to ID format
                selected_name = selected.iloc[0].get('Candidate Name', '')
                if isinstance(selected_name, str):
                    st.session_state.selected_draft = selected_name.lower().replace(' ', '-')
                else:
                    st.session_state.selected_draft = ''
                
                # Add JavaScript to scroll to the selected draft's section
                js = f"""
                <script>
                    // Function to scroll to element
                    function scrollToElement() {{
                        const element = document.getElementById('{st.session_state.selected_draft}');
                        if (element) {{
                            // Scroll to the element with smooth behavior
                            element.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
                            // Add some padding to the top
                            window.scrollBy(0, -20);
                        }}
                    }}

                    // Try to scroll immediately
                    scrollToElement();

                    // Also try after a short delay to ensure everything is loaded
                    setTimeout(scrollToElement, 500);
                    
                    // And try again after a longer delay
                    setTimeout(scrollToElement, 1000);
                </script>
                """
                st.components.v1.html(js, height=0)
                st.rerun()

    # Save changes to follow-up status
    if st.button("💾 Save Changes"):
        try:
            # Get the current state of the dataframe
            updated_df = edited_df
            
            # Update each draft's status
            for i, row in updated_df.iterrows():
                try:
                    # Convert the date to ISO format with timezone
                    if pd.notna(row['Follow-up Date']):
                        # Convert to datetime and format with timezone
                        follow_up_date = pd.to_datetime(row['Follow-up Date']).tz_localize('UTC').isoformat()
                    else:
                        follow_up_date = None
                except (AttributeError, ValueError) as e:
                    st.error(f"Error processing date: {str(e)}")
                    follow_up_date = None
                    
                data = {
                    'contact_status': bool(row['Contacted']),
                    'follow_up_required': bool(row['Follow-up Required']),
                    'follow_up_date': follow_up_date,
                    'updated_at': datetime.now(UTC).isoformat()
                }
                
                response = supabase.table('recruiter_notes')\
                    .update(data)\
                    .eq('id', drafts[i]['id'])\
                    .execute()
                
                if hasattr(response, 'error') and response.error:
                    st.error(f"Error updating status: {response.error}")
                    return
            
            st.success("Changes saved successfully!")
            st.session_state.refresh_key = time.time()
            st.rerun()
            
        except Exception as e:
            st.error(f"Error updating status: {str(e)}")
            st.error("Please try again or contact support if the issue persists.")

    # Display selected candidate details at the top first
    if st.session_state.selected_draft:
        selected_draft_obj = next(
            (d for d in drafts if str(d.get('resumes', {}).get('resumes_pii', [{}])[0].get('full_name', '') or '').lower().replace(' ', '-') == st.session_state.selected_draft),
            None
        )
        if selected_draft_obj:
            resume = selected_draft_obj.get('resumes', {})
            pii_data = resume.get('resumes_pii', [{}])[0] if resume.get('resumes_pii') else {}
            full_name = str(pii_data.get('full_name', '') or '')
            st.subheader("📝 Selected Draft Details")
            with st.expander(f"👤 {full_name or 'N/A'} - {resume.get('current_or_last_job_title', 'N/A')}", expanded=True):
                # Candidate summary
                st.markdown("#### Candidate Summary")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Name:** {pii_data.get('full_name', 'N/A')}")
                    st.markdown(f"**Current Role:** {resume.get('current_or_last_job_title', 'N/A')}")
                    st.markdown(f"**Location:** {resume.get('location', 'N/A')}")
                with col2:
                    st.markdown(f"**Email:** {pii_data.get('email', 'N/A')}")
                    st.markdown(f"**Phone:** {pii_data.get('phone', 'N/A')}")
                
                # Outreach message
                st.markdown("#### Outreach Message")
                outreach_message = st.text_area(
                    "Message:",
                    value=selected_draft_obj['outreach_message'],
                    height=150
                )
                
                # Screening questions
                st.markdown("#### Screening Questions")
                screening_questions = st.text_area(
                    "Questions:",
                    value=selected_draft_obj['screening_questions'],
                    height=100
                )
                
                # Save changes and move to tracker
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 Save Changes", key=f"save_selected_{selected_draft_obj['id']}"):
                        try:
                            data = {
                                'outreach_message': outreach_message,
                                'screening_questions': screening_questions,
                                'updated_at': datetime.now(UTC).isoformat()
                            }
                            
                            response = supabase.table('recruiter_notes')\
                                .update(data)\
                                .eq('id', selected_draft_obj['id'])\
                                .execute()
                            
                            if hasattr(response, 'error') and response.error:
                                st.error(f"Error saving changes: {response.error}")
                            else:
                                st.success("Changes saved successfully!")
                                st.session_state.refresh_key = time.time()
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Error saving changes: {str(e)}")
                
                with col2:
                    if st.button("✅ Mark as Contacted", key=f"contact_selected_{selected_draft_obj['id']}"):
                        try:
                            data = {
                                'contact_status': True,
                                'outreach_message': outreach_message,
                                'screening_questions': screening_questions,
                                'follow_up_required': selected_draft_obj.get('follow_up_required', False),
                                'follow_up_date': selected_draft_obj.get('follow_up_date'),
                                'updated_at': datetime.now(UTC).isoformat()
                            }
                            
                            response = supabase.table('recruiter_notes')\
                                .update(data)\
                                .eq('id', selected_draft_obj['id'])\
                                .execute()
                            
                            if hasattr(response, 'error') and response.error:
                                st.error(f"Error marking as contacted: {response.error}")
                            else:
                                st.success("Candidate moved to tracker!")
                                st.session_state.refresh_key = time.time()
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Error marking as contacted: {str(e)}")
                
                # Update follow-up status
                with st.form(key=f"update_followup_selected_{selected_draft_obj['id']}"):
                    st.markdown("#### Update Follow-up Status")
                    new_follow_up_required = st.checkbox("Follow-up Required", value=selected_draft_obj.get('follow_up_required', False))
                    new_follow_up_date = st.date_input(
                        "Follow-up Date",
                        value=pd.to_datetime(selected_draft_obj.get('follow_up_date')).date() if selected_draft_obj.get('follow_up_date') else None
                    )
                    
                    if st.form_submit_button("Update Follow-up Status"):
                        try:
                            # Convert the date to ISO format with timezone
                            if new_follow_up_date:
                                follow_up_date = pd.to_datetime(new_follow_up_date).tz_localize('UTC').isoformat()
                            else:
                                follow_up_date = None
                                
                            data = {
                                'follow_up_required': new_follow_up_required,
                                'follow_up_date': follow_up_date,
                                'updated_at': datetime.now(UTC).isoformat()
                            }
                            
                            response = supabase.table('recruiter_notes')\
                                .update(data)\
                                .eq('id', selected_draft_obj['id'])\
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
                st.markdown(f"*Created: {format_timestamp(selected_draft_obj['created_at'])}*")
                if selected_draft_obj.get('updated_at'):
                    st.markdown(f"*Last Updated: {format_timestamp(selected_draft_obj['updated_at'])}*")

    # Divider for the rest
    st.markdown("---")
    st.subheader("📝 All Draft Details")

    # Display remaining drafts
    for draft in drafts:
        resume = draft.get('resumes', {})
        pii_data = resume.get('resumes_pii', [{}])[0] if resume.get('resumes_pii') else {}
        full_name = str(pii_data.get('full_name', '') or '')
        anchor_id = slugify(full_name)
        if anchor_id == st.session_state.selected_draft:
            continue  # Already shown above

        with st.expander(f"👤 {full_name or 'N/A'} - {resume.get('current_or_last_job_title', 'N/A')}", expanded=False):
            # Candidate summary
            st.markdown("#### Candidate Summary")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Name:** {pii_data.get('full_name', 'N/A')}")
                st.markdown(f"**Current Role:** {resume.get('current_or_last_job_title', 'N/A')}")
                st.markdown(f"**Location:** {resume.get('location', 'N/A')}")
            with col2:
                st.markdown(f"**Email:** {pii_data.get('email', 'N/A')}")
                st.markdown(f"**Phone:** {pii_data.get('phone', 'N/A')}")
            
            # Last outreach message
            st.markdown("#### Last Outreach Message")
            st.text_area(
                "Message:",
                value=draft['outreach_message'],
                height=150,
                key=f"message_{draft['id']}_selected"
            )

            # Screening questions
            st.markdown("#### Screening Questions")
            st.text_area(
                "Questions:",
                value=draft['screening_questions'],
                height=100,
                key=f"questions_{draft['id']}_selected"
            )

            # Follow-up status
            st.markdown("#### Follow-up Status")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Follow-up Required:** {'Yes' if draft.get('follow_up_required') else 'No'}")
            with col2:
                follow_up_date = draft.get('follow_up_date')
                if follow_up_date:
                    st.markdown(f"**Follow-up Date:** {format_timestamp(follow_up_date)}")

            # Update follow-up status
            with st.form(key=f"update_followup_{draft['id']}_remaining"):
                st.markdown("#### Update Follow-up Status")
                new_follow_up_required = st.checkbox("Follow-up Required", value=draft.get('follow_up_required', False))
                new_follow_up_date = st.date_input(
                    "Follow-up Date",
                    value=pd.to_datetime(draft.get('follow_up_date')).date() if draft.get('follow_up_date') else None
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
                            .eq('id', draft['id'])\
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
            st.markdown(f"*First Contact: {format_timestamp(draft['created_at'])}*")
            if draft.get('updated_at'):
                st.markdown(f"*Last Updated: {format_timestamp(draft['updated_at'])}*")

    # Pagination
    total_pages = (total_count + st.session_state.drafts_per_page - 1) // st.session_state.drafts_per_page
    
    if total_pages > 1:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col1:
            if st.session_state.drafts_page > 1:
                if st.button("← Previous"):
                    st.session_state.drafts_page -= 1
                    st.session_state.selected_draft = None
                    st.rerun()
        
        with col2:
            st.markdown(f"**Page {st.session_state.drafts_page} of {total_pages}**")
        
        with col3:
            if st.session_state.drafts_page < total_pages:
                if st.button("Next →"):
                    st.session_state.drafts_page += 1
                    st.session_state.selected_draft = None
                    st.rerun()

if __name__ == "__main__":
    main() 