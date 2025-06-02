import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import io

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

def get_candidate_metrics():
    """Get summary metrics from the candidates table"""
    try:
        # Get all candidates
        response = supabase.table('resumes').select('*').execute()
        candidates = response.data
        
        if not candidates:
            return None
            
        # Calculate metrics
        total_candidates = len(candidates)
        
        # Get top job titles
        job_titles = [c['current_or_last_job_title'] for c in candidates if c['current_or_last_job_title']]
        top_job_titles = Counter(job_titles).most_common(3)
        
        # Get most common skill
        all_skills = []
        for c in candidates:
            if c['skills']:
                all_skills.extend(c['skills'])
        most_common_skill = Counter(all_skills).most_common(1)[0][0] if all_skills else "No skills found"
        
        # Get top location
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

def create_job_title_chart(candidates):
    """Create bar chart of job titles"""
    job_titles = [c['current_or_last_job_title'] for c in candidates if c['current_or_last_job_title']]
    title_counts = Counter(job_titles)
    
    df = pd.DataFrame({
        'Job Title': list(title_counts.keys()),
        'Count': list(title_counts.values())
    })
    
    fig = px.bar(df, x='Job Title', y='Count', title='Candidates by Job Title')
    fig.update_layout(xaxis_tickangle=-45)
    return fig

def create_location_chart(candidates):
    """Create pie chart of locations"""
    locations = [c['location'] for c in candidates if c['location']]
    location_counts = Counter(locations)
    
    df = pd.DataFrame({
        'Location': list(location_counts.keys()),
        'Count': list(location_counts.values())
    })
    
    fig = px.pie(df, values='Count', names='Location', title='Candidates by Location')
    return fig

def create_skill_chart(candidates):
    """Create bar chart of top skills"""
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

def get_recent_candidates(candidates, limit=5):
    """Get most recently uploaded candidates"""
    # Sort by created_at in descending order
    sorted_candidates = sorted(
        candidates,
        key=lambda x: x['created_at'],
        reverse=True
    )
    
    # Take the most recent ones
    recent = sorted_candidates[:limit]
    
    # Create a DataFrame for display
    df = pd.DataFrame([{
        'Name': c['full_name'],
        'Job Title': c['current_or_last_job_title'],
        'Location': c['location'],
        'Upload Date': pd.to_datetime(c['created_at']).strftime('%Y-%m-%d')
    } for c in recent])
    
    return df

def main():
    st.set_page_config(
        page_title="SkillQ - Recruiter Dashboard",
        page_icon="📊",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not st.session_state.authenticated:
        st.warning("Please login to access this page")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

    # Add back button at the top
    if st.button("← Back to Home"):
        st.switch_page("pages/home.py")

    st.title("📊 Recruiter Dashboard")
    
    # Get metrics
    metrics = get_candidate_metrics()
    
    if not metrics:
        st.warning("No candidate data available. Please upload some resumes first.")
        return
    
    # Summary Metrics Section
    st.subheader("📈 Summary Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Candidates", metrics['total_candidates'])
    
    with col2:
        st.metric("Top Job Titles", ", ".join([f"{title} ({count})" for title, count in metrics['top_job_titles']]))
    
    with col3:
        st.metric("Most Common Skill", metrics['most_common_skill'])
    
    with col4:
        st.metric("Top Location", metrics['top_location'])
    
    # Charts Section
    st.subheader("📊 Analytics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(create_job_title_chart(metrics['candidates']), use_container_width=True)
        st.plotly_chart(create_location_chart(metrics['candidates']), use_container_width=True)
    
    with col2:
        st.plotly_chart(create_skill_chart(metrics['candidates']), use_container_width=True)
    
    # Recent Activity Section
    st.subheader("🕒 Recent Activity")
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