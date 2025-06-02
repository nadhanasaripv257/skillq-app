import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from collections import Counter
from functools import lru_cache
import time
from datetime import datetime, UTC

# Load environment variables
load_dotenv()

# Check if environment variables are loaded
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=supabase_url,
    supabase_key=supabase_key
)

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'page' not in st.session_state:
        st.session_state.page = None
    if 'dashboard_initialized' not in st.session_state:
        st.session_state.dashboard_initialized = False
    if 'refresh_key' not in st.session_state:
        st.session_state.refresh_key = time.time()

@st.cache_data(ttl=300, show_spinner=False)
def get_user_profile(refresh_key=None):
    """Get user profile from Supabase"""
    try:
        # Get the user's ID from auth.users
        user_response = supabase.auth.get_user()
        
        if not user_response.user:
            st.error("No user found in auth response")
            return None
        
        user_id = user_response.user.id
        
        # Get the profile data
        profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if profile_response.data:
            return profile_response.data[0]
        
        # If no profile exists, return a default profile
        return {
            'user_id': user_id,
            'full_name': user_response.user.email.split('@')[0],
            'company': '',
            'role': '',
            'phone': '',
            'linkedin': '',
            'created_at': datetime.now(UTC).isoformat(),
            'updated_at': datetime.now(UTC).isoformat()
        }
    except Exception as e:
        st.error(f"Error fetching profile: {str(e)}")
        return None

@st.cache_data(ttl=300, show_spinner=False)
def get_candidate_metrics(refresh_key=None):
    """Get summary metrics using direct query"""
    try:
        # Direct query approach
        response = supabase.table('resumes').select('*').execute()
        candidates = response.data
        
        if not candidates:
            st.warning("No candidates found in the database")
            return None
            
        # Process data
        total_candidates = len(candidates)
        
        # Process job titles
        job_titles = [c['current_or_last_job_title'] for c in candidates if c['current_or_last_job_title']]
        job_title_counts = dict(Counter(job_titles))
        top_job_titles = Counter(job_titles).most_common(3)
        
        # Process skills
        all_skills = []
        for c in candidates:
            if c.get('skills'):
                all_skills.extend(c['skills'])
        skill_counts = dict(Counter(all_skills))
        most_common_skill = Counter(all_skills).most_common(1)[0][0] if all_skills else "No skills found"
        
        # Process locations
        locations = [c['location'] for c in candidates if c['location']]
        location_counts = dict(Counter(locations))
        top_location = Counter(locations).most_common(1)[0][0] if locations else "No location found"
        
        # Get recent candidates
        recent_candidates = sorted(
            candidates,
            key=lambda x: x['created_at'],
            reverse=True
        )[:5]
        
        return {
            'total_candidates': total_candidates,
            'top_job_titles': top_job_titles,
            'most_common_skill': most_common_skill,
            'top_location': top_location,
            'candidates': recent_candidates,
            'job_title_counts': job_title_counts,
            'location_counts': location_counts,
            'skill_counts': skill_counts
        }
    except Exception as e:
        st.error(f"Error fetching metrics: {str(e)}")
        return None

@st.cache_data(ttl=300, show_spinner=False)
def create_job_title_chart(metrics, refresh_key=None):
    """Create job title chart with cached data"""
    try:
        if 'job_title_counts' in metrics:
            job_title_counts = metrics['job_title_counts'] or {}
        else:
            job_titles = [c.get('current_or_last_job_title') for c in metrics.get('candidates', []) 
                         if isinstance(c, dict) and c.get('current_or_last_job_title')]
            job_title_counts = dict(Counter(job_titles))
        
        if not job_title_counts:
            return px.bar(title='No Job Title Data Available')
            
        df = pd.DataFrame({
            'Job Title': list(job_title_counts.keys()),
            'Count': list(job_title_counts.values())
        })
        
        df = df.sort_values('Count', ascending=False).head(10)
        
        fig = px.bar(
            df,
            x='Job Title',
            y='Count',
            title='Top 10 Job Titles',
            color='Count',
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis_title='Job Title',
            yaxis_title='Number of Candidates',
            showlegend=False,
            height=500,
            margin=dict(b=100)
        )
        
        fig.update_traces(
            marker_line_width=0,
            marker_line_color='white'
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating job title chart: {str(e)}")
        return px.bar(title='Error Loading Job Title Data')

@st.cache_data(ttl=300, show_spinner=False)
def create_location_chart(metrics, refresh_key=None):
    """Create location chart with cached data"""
    try:
        if 'location_counts' in metrics:
            location_counts = metrics['location_counts'] or {}
        else:
            locations = [c.get('location') for c in metrics.get('candidates', []) 
                        if isinstance(c, dict) and c.get('location')]
            location_counts = dict(Counter(locations))
        
        if not location_counts:
            return px.pie(title='No Location Data Available')
            
        df = pd.DataFrame({
            'Location': list(location_counts.keys()),
            'Count': list(location_counts.values())
        })
        fig = px.pie(df, values='Count', names='Location', title='Candidates by Location')
        return fig
    except Exception as e:
        st.error(f"Error creating location chart: {str(e)}")
        return px.pie(title='Error Loading Location Data')

@st.cache_data(ttl=300, show_spinner=False)
def create_skill_chart(metrics, refresh_key=None):
    """Create skill chart with cached data"""
    try:
        if 'skill_counts' in metrics:
            skill_counts = metrics['skill_counts'] or {}
        else:
            all_skills = []
            for c in metrics.get('candidates', []):
                if isinstance(c, dict) and c.get('skills'):
                    all_skills.extend(c['skills'])
            skill_counts = dict(Counter(all_skills))
        
        if not skill_counts:
            return px.bar(title='No Skills Data Available')
            
        top_skills = dict(sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15])
        
        df = pd.DataFrame({
            'Skill': list(top_skills.keys()),
            'Count': list(top_skills.values())
        })
        
        fig = px.bar(
            df,
            x='Skill',
            y='Count',
            title='Top 15 Skills',
            color='Count',
            color_continuous_scale='Viridis'
        )
        
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis_title='Skill',
            yaxis_title='Number of Candidates',
            showlegend=False,
            height=500,
            margin=dict(b=100)
        )
        
        fig.update_traces(
            marker_line_width=0,
            marker_line_color='white'
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating skill chart: {str(e)}")
        return px.bar(title='Error Loading Skills Data')

@st.cache_data(ttl=300, show_spinner=False)
def get_recent_candidates(metrics, refresh_key=None):
    """Get recent candidates with cached data"""
    try:
        if isinstance(metrics.get('candidates'), list) and len(metrics['candidates']) > 0 and isinstance(metrics['candidates'][0], dict):
            recent_candidates = metrics['candidates']
        else:
            recent_candidates = metrics.get('candidates', []) or []
        
        if not recent_candidates:
            return pd.DataFrame(columns=['Name', 'Job Title', 'Location', 'Upload Date'])
            
        df = pd.DataFrame([{
            'Name': c.get('full_name', 'N/A'),
            'Job Title': c.get('current_or_last_job_title', 'N/A'),
            'Location': c.get('location', 'N/A'),
            'Upload Date': pd.to_datetime(c.get('created_at')).strftime('%Y-%m-%d') if c.get('created_at') else 'N/A'
        } for c in recent_candidates])
        return df
    except Exception as e:
        st.error(f"Error getting recent candidates: {str(e)}")
        return pd.DataFrame(columns=['Name', 'Job Title', 'Location', 'Upload Date'])

def main():
    st.set_page_config(
        page_title="SkillQ - Home",
        page_icon="🏠",
        layout="wide"
    )
    
    # Debug information after page config
    if not supabase_url or not supabase_key:
        st.error("Missing Supabase credentials. Please check your environment variables.")
        st.write("Debug - SUPABASE_URL:", supabase_url)
        st.write("Debug - SUPABASE_KEY:", supabase_key[:10] + "..." if supabase_key else None)
        st.stop()

    # Test Supabase connection
    try:
        test_response = supabase.auth.get_user()
        st.write("Debug - Supabase Connection Test:", test_response)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {str(e)}")
        st.write("Debug - Connection Error Details:", e)
        st.stop()
    
    # Initialize session state
    initialize_session_state()
    
    # Force refresh on first load or when coming from login
    if st.session_state.page != "Home":
        st.session_state.page = "Home"
        st.session_state.refresh_key = time.time()
        st.session_state.dashboard_initialized = False
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.session_state.page = "Login"
            st.switch_page("pages/login.py")
        return

    # Get user profile
    profile = get_user_profile(st.session_state.get("refresh_key"))
    if not profile:
        st.error("Error loading profile. Please try logging in again.")
        if st.button("Go to Login"):
            st.session_state.page = "Login"
            st.switch_page("pages/login.py")
        return

    display_name = profile.get('full_name', '') if profile else st.session_state.user_email

    # Create a container for the header with logout button
    header_container = st.container()
    with header_container:
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            st.title("🏠 Welcome to SkillQ")
            st.write(f"Hello, {display_name}!")
        with col2:
            st.write("")  # Add some vertical space
            if st.button("Logout", key="logout_top"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.dashboard_initialized = False
                st.session_state.page = "Login"
                st.session_state.refresh_key = time.time()
                st.switch_page("pages/login.py")

    # Create three columns for different sections
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📄 Resume Management")
        st.write("Upload and manage candidate resumes")
        if st.button("Go to Upload Page"):
            st.session_state.page = "Upload"
            st.switch_page("pages/upload.py")

    with col2:
        st.subheader("💬 Ask SkillQ")
        st.write("Get insights about candidate skills")
        if st.button("Start Chat"):
            st.session_state.page = "Chat"
            st.switch_page("pages/chat.py")

    with col3:
        st.subheader("👤 Profile Settings")
        st.write("Update your profile information")
        if st.button("Edit Profile"):
            st.session_state.page = "Profile"
            st.switch_page("pages/profile.py")

    # Add My Drafts section
    st.markdown("---")
    st.subheader("📁 My Drafts")
    st.write("View and manage your saved outreach messages")
    if st.button("View My Drafts", use_container_width=True):
        st.session_state.page = "Drafts"
        st.switch_page("pages/drafts.py")

    # Add Candidate Tracker section
    st.markdown("---")
    st.subheader("👥 Candidate Tracker")
    st.write("Track your contacted candidates and follow-ups")
    if st.button("View Candidate Tracker", use_container_width=True):
        st.session_state.page = "Tracker"
        st.switch_page("pages/candidate_tracker.py")

    # Dashboard Section - Always show when on home page
    st.markdown("---")
    st.subheader("📊 Quick Look at Your Candidate Portfolio")
    
    # Add refresh button
    if st.button("🔄 Refresh Dashboard"):
        st.session_state.refresh_key = time.time()
        st.rerun()
    
    # Always attempt to load dashboard data
    metrics = None
    with st.spinner('Loading dashboard data...'):
        try:
            metrics = get_candidate_metrics(st.session_state.get("refresh_key"))
        except Exception as e:
            st.error(f"Error loading dashboard: {str(e)}")
            st.info("Please try refreshing the page or logging in again.")
    
    # Show dashboard content if we have data
    if metrics:
        # Summary Metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Candidates", metrics['total_candidates'])
        with col2:
            st.metric("Top Location", metrics['top_location'])
            
        # Charts - Load them lazily
        st.subheader("📊 Analytics")
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            with st.spinner('Loading job title chart...'):
                st.plotly_chart(create_job_title_chart(metrics, st.session_state.get("refresh_key")), use_container_width=True)
            with st.spinner('Loading location chart...'):
                st.plotly_chart(create_location_chart(metrics, st.session_state.get("refresh_key")), use_container_width=True)
                
        with chart_col2:
            with st.spinner('Loading skills chart...'):
                st.plotly_chart(create_skill_chart(metrics, st.session_state.get("refresh_key")), use_container_width=True)
                
        # Recent Activity
        st.subheader("🕒 Recent Activity")
        with st.spinner('Loading recent candidates...'):
            recent_candidates = get_recent_candidates(metrics, st.session_state.get("refresh_key"))
            st.dataframe(recent_candidates, use_container_width=True)
    else:
        st.warning("No candidate data available. Please upload some resumes first.")

if __name__ == "__main__":
    main() 