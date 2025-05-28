import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from collections import Counter
from functools import lru_cache

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

def get_user_profile():
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

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_candidate_metrics():
    """Get summary metrics from the candidates table with a single optimized query"""
    try:
        # Single query to get all necessary data
        response = supabase.table('resumes').select(
            'id, current_or_last_job_title, location, skills, created_at, full_name'
        ).execute()
        
        candidates = response.data
        if not candidates:
            return None
            
        # Process data once
        total_candidates = len(candidates)
        
        # Process job titles
        job_titles = [c['current_or_last_job_title'] for c in candidates if c['current_or_last_job_title']]
        top_job_titles = Counter(job_titles).most_common(3)
        
        # Process skills
        all_skills = []
        for c in candidates:
            if c['skills']:
                all_skills.extend(c['skills'])
        most_common_skill = Counter(all_skills).most_common(1)[0][0] if all_skills else "No skills found"
        
        # Process locations
        locations = [c['location'] for c in candidates if c['location']]
        top_location = Counter(locations).most_common(1)[0][0] if locations else "No location found"
        
        return {
            'total_candidates': total_candidates,
            'top_job_titles': top_job_titles,
            'most_common_skill': most_common_skill,
            'top_location': top_location,
            'candidates': candidates
        }
    except Exception as e:
        st.error(f"Error fetching metrics: {str(e)}")
        return None

@st.cache_data(ttl=300)
def create_job_title_chart(candidates):
    job_titles = [c['current_or_last_job_title'] for c in candidates if c['current_or_last_job_title']]
    title_counts = Counter(job_titles)
    df = pd.DataFrame({
        'Job Title': list(title_counts.keys()),
        'Count': list(title_counts.values())
    })
    fig = px.bar(df, x='Job Title', y='Count', title='Candidates by Job Title')
    fig.update_layout(xaxis_tickangle=-45)
    return fig

@st.cache_data(ttl=300)
def create_location_chart(candidates):
    locations = [c['location'] for c in candidates if c['location']]
    location_counts = Counter(locations)
    df = pd.DataFrame({
        'Location': list(location_counts.keys()),
        'Count': list(location_counts.values())
    })
    fig = px.pie(df, values='Count', names='Location', title='Candidates by Location')
    return fig

@st.cache_data(ttl=300)
def create_skill_chart(candidates):
    all_skills = []
    for c in candidates:
        if c['skills']:
            all_skills.extend(c['skills'])
    skill_counts = Counter(all_skills)
    top_skills = dict(skill_counts.most_common(10))
    df = pd.DataFrame({
        'Skill': list(top_skills.keys()),
        'Count': list(top_skills.values())
    })
    fig = px.bar(df, x='Skill', y='Count', title='Top 10 Skills')
    fig.update_layout(xaxis_tickangle=-45)
    return fig

@st.cache_data(ttl=300)
def get_recent_candidates(candidates, limit=5):
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x['created_at'],
        reverse=True
    )
    recent = sorted_candidates[:limit]
    df = pd.DataFrame([{
        'Name': c['full_name'],
        'Job Title': c['current_or_last_job_title'],
        'Location': c['location'],
        'Upload Date': pd.to_datetime(c['created_at']).strftime('%Y-%m-%d')
    } for c in recent])
    return df

def main():
    st.set_page_config(
        page_title="SkillQ - Home",
        page_icon="🏠",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

    # Get user profile
    profile = get_user_profile()
    display_name = profile.get('full_name', '') if profile else st.session_state.user_email

    st.title("🏠 Welcome to SkillQ")
    st.write(f"Hello, {display_name}!")

    # Create three columns for different sections
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("📄 Resume Management")
        st.write("Upload and manage candidate resumes")
        if st.button("Go to Upload Page"):
            st.switch_page("pages/upload.py")

    with col2:
        st.subheader("💬 Ask SkillQ")
        st.write("Get insights about candidate skills")
        if st.button("Start Chat"):
            st.switch_page("pages/chat.py")

    with col3:
        st.subheader("👤 Profile Settings")
        st.write("Update your profile information")
        if st.button("Edit Profile"):
            st.switch_page("pages/profile.py")

    # Dashboard Section
    st.markdown("---")
    st.subheader("📊 Quick Look at Your Candidate Portfolio")
    
    # Show loading spinner while fetching data
    with st.spinner('Loading dashboard data...'):
        metrics = get_candidate_metrics()
        
    if not metrics:
        st.warning("No candidate data available. Please upload some resumes first.")
    else:
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
                st.plotly_chart(create_job_title_chart(metrics['candidates']), use_container_width=True)
            with st.spinner('Loading location chart...'):
                st.plotly_chart(create_location_chart(metrics['candidates']), use_container_width=True)
                
        with chart_col2:
            with st.spinner('Loading skills chart...'):
                st.plotly_chart(create_skill_chart(metrics['candidates']), use_container_width=True)
                
        # Recent Activity
        st.subheader("🕒 Recent Activity")
        with st.spinner('Loading recent candidates...'):
            recent_candidates = get_recent_candidates(metrics['candidates'])
            st.dataframe(recent_candidates, use_container_width=True)

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 