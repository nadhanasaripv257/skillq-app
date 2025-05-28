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
    """Get summary metrics from the dashboard_metrics materialized view or fallback to direct query"""
    try:
        # Try to get data from the materialized view first
        try:
            response = supabase.table('dashboard_metrics').select('*').execute()
            if response.data:
                metrics = response.data[0]
                return {
                    'total_candidates': metrics['total_candidates'],
                    'top_job_titles': sorted(
                        [(title, count) for title, count in (metrics['job_title_counts'] or {}).items()],
                        key=lambda x: x[1],
                        reverse=True
                    )[:3],
                    'most_common_skill': max((metrics['skill_counts'] or {}).items(), key=lambda x: x[1])[0] if metrics['skill_counts'] else "No skills found",
                    'top_location': max((metrics['location_counts'] or {}).items(), key=lambda x: x[1])[0] if metrics['location_counts'] else "No location found",
                    'candidates': metrics['recent_candidates'] or [],
                    'job_title_counts': metrics['job_title_counts'] or {},
                    'location_counts': metrics['location_counts'] or {},
                    'skill_counts': metrics['skill_counts'] or {}
                }
        except Exception as view_error:
            st.warning("Dashboard view not available yet, using direct query...")
            
        # Fallback to direct query if view is not available
        response = supabase.table('resumes').select('*').execute()
        candidates = response.data
        
        if not candidates:
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

@st.cache_data(ttl=300)
def create_job_title_chart(metrics):
    try:
        if 'job_title_counts' in metrics:
            # Using materialized view data
            job_title_counts = metrics['job_title_counts'] or {}
        else:
            # Using direct query data
            job_titles = [c.get('current_or_last_job_title') for c in metrics.get('candidates', []) 
                         if isinstance(c, dict) and c.get('current_or_last_job_title')]
            job_title_counts = dict(Counter(job_titles))
        
        if not job_title_counts:
            return px.bar(title='No Job Title Data Available')
            
        # Create DataFrame
        df = pd.DataFrame({
            'Job Title': list(job_title_counts.keys()),
            'Count': list(job_title_counts.values())
        })
        
        # Sort by count in descending order and take top 10
        df = df.sort_values('Count', ascending=False).head(10)
        
        # Create bar chart
        fig = px.bar(
            df,
            x='Job Title',
            y='Count',
            title='Top 10 Job Titles',
            color='Count',  # Add color gradient based on count
            color_continuous_scale='Viridis'  # Use a nice color scale
        )
        
        # Update layout for better readability
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis_title='Job Title',
            yaxis_title='Number of Candidates',
            showlegend=False,
            height=500,  # Make the chart taller
            margin=dict(b=100)  # Add bottom margin for rotated labels
        )
        
        # Update traces for better appearance
        fig.update_traces(
            marker_line_width=0,  # Remove bar borders
            marker_line_color='white'  # White borders if needed
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating job title chart: {str(e)}")
        return px.bar(title='Error Loading Job Title Data')

@st.cache_data(ttl=300)
def create_location_chart(metrics):
    try:
        if 'location_counts' in metrics:
            # Using materialized view data
            location_counts = metrics['location_counts'] or {}
        else:
            # Using direct query data
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

@st.cache_data(ttl=300)
def create_skill_chart(metrics):
    try:
        if 'skill_counts' in metrics:
            # Using materialized view data
            skill_counts = metrics['skill_counts'] or {}
        else:
            # Using direct query data
            all_skills = []
            for c in metrics.get('candidates', []):
                if isinstance(c, dict) and c.get('skills'):
                    all_skills.extend(c['skills'])
            skill_counts = dict(Counter(all_skills))
        
        if not skill_counts:
            return px.bar(title='No Skills Data Available')
            
        # Sort skills by count in descending order and take top 15
        top_skills = dict(sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:15])
        
        # Create DataFrame
        df = pd.DataFrame({
            'Skill': list(top_skills.keys()),
            'Count': list(top_skills.values())
        })
        
        # Create bar chart
        fig = px.bar(
            df,
            x='Skill',
            y='Count',
            title='Top 15 Skills',
            color='Count',  # Add color gradient based on count
            color_continuous_scale='Viridis'  # Use a nice color scale
        )
        
        # Update layout for better readability
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis_title='Skill',
            yaxis_title='Number of Candidates',
            showlegend=False,
            height=500,  # Make the chart taller
            margin=dict(b=100)  # Add bottom margin for rotated labels
        )
        
        # Update traces for better appearance
        fig.update_traces(
            marker_line_width=0,  # Remove bar borders
            marker_line_color='white'  # White borders if needed
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating skill chart: {str(e)}")
        return px.bar(title='Error Loading Skills Data')

@st.cache_data(ttl=300)
def get_recent_candidates(metrics):
    try:
        if isinstance(metrics.get('candidates'), list) and len(metrics['candidates']) > 0 and isinstance(metrics['candidates'][0], dict):
            # Using direct query data
            recent_candidates = metrics['candidates']
        else:
            # Using materialized view data
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

def clear_cache():
    """Clear all cached data"""
    st.cache_data.clear()

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
    if not profile:
        st.error("Error loading profile. Please try logging in again.")
        if st.button("Go to Login"):
            st.switch_page("login.py")
        return

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
        # Clear cache when loading dashboard
        clear_cache()
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
                st.plotly_chart(create_job_title_chart(metrics), use_container_width=True)
            with st.spinner('Loading location chart...'):
                st.plotly_chart(create_location_chart(metrics), use_container_width=True)
                
        with chart_col2:
            with st.spinner('Loading skills chart...'):
                st.plotly_chart(create_skill_chart(metrics), use_container_width=True)
                
        # Recent Activity
        st.subheader("🕒 Recent Activity")
        with st.spinner('Loading recent candidates...'):
            recent_candidates = get_recent_candidates(metrics)
            st.dataframe(recent_candidates, use_container_width=True)

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        clear_cache()  # Clear cache on logout
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 