import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import json
from datetime import datetime, UTC
from backend.openai_client import OpenAIClient
import pandas as pd
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(
    supabase_url=st.secrets["SUPABASE_URL"],
    supabase_key=st.secrets["SUPABASE_KEY"]
)

# Initialize OpenAI client
openai_client = OpenAIClient()

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None
    if 'last_query' not in st.session_state:
        st.session_state.last_query = None
    if 'current_filters' not in st.session_state:
        st.session_state.current_filters = None

def get_candidate_skills():
    """Get all candidate skills from resumes and organize them by category"""
    try:
        response = supabase.table('resumes').select('skills, skill_categories').execute()
        all_skills = set()
        skill_categories = {}
        
        # Default categories
        default_categories = {
            'Technical & Tools': [],  # Combined category
            'Soft Skills': [],
            'Management & Leadership': [],
            'Other': []
        }
        
        for resume in response.data:
            skills_data = resume['skills']
            categories_data = resume.get('skill_categories', {})
            
            # Process skills
            if isinstance(skills_data, str):
                try:
                    skills_data = json.loads(skills_data)
                    if isinstance(skills_data, dict) and 'skills' in skills_data:
                        all_skills.update(skills_data['skills'])
                    else:
                        all_skills.update(skills_data)
                except json.JSONDecodeError:
                    all_skills.add(skills_data)
            elif isinstance(skills_data, list):
                all_skills.update(skills_data)
            elif isinstance(skills_data, dict) and 'skills' in skills_data:
                all_skills.update(skills_data['skills'])
        
        # Categorize skills
        for skill in sorted(all_skills):
            # Check if skill is in any category from the database
            categorized = False
            for category, skills in categories_data.items():
                if skill in skills:
                    if category not in skill_categories:
                        skill_categories[category] = []
                    skill_categories[category].append(skill)
                    categorized = True
                    break
            
            # If not categorized, use default categories
            if not categorized:
                # Technical & Tools (combined category)
                if any(tech in skill.lower() for tech in ['programming', 'coding', 'development', 'software', 'technical', 'engineering', 'database', 'cloud', 'api', 'web', 'mobile', 'devops', 'security', 'testing', 'tool', 'platform', 'system', 'application', 'crm', 'erp', 'jira', 'git', 'docker', 'kubernetes']):
                    default_categories['Technical & Tools'].append(skill)
                # Management & Leadership
                elif any(lead in skill.lower() for lead in ['management', 'leadership', 'team', 'project', 'strategy', 'planning', 'budget', 'resource']):
                    default_categories['Management & Leadership'].append(skill)
                # Soft Skills
                elif any(soft in skill.lower() for soft in ['problem solving', 'critical thinking', 'adaptability', 'creativity', 'collaboration', 'time management', 'organization', 'communication', 'presentation', 'writing', 'speaking', 'negotiation', 'interpersonal']):
                    default_categories['Soft Skills'].append(skill)
                else:
                    default_categories['Other'].append(skill)
        
        # Merge custom categories with default categories
        for category, skills in skill_categories.items():
            if category not in default_categories:
                default_categories[category] = []
            default_categories[category].extend(skills)
        
        return default_categories
    except Exception as e:
        st.error(f"Error loading skills: {str(e)}")
        return {}

def display_skills(skills_by_category):
    """Display skills organized by category"""
    if not skills_by_category:
        st.info("No skills found. Please upload some resumes first.")
        return
        
    for category, skills in skills_by_category.items():
        if skills:  # Only show categories that have skills
            with st.expander(f"📚 {category} ({len(skills)})", expanded=True):
                # Create columns for better layout
                cols = st.columns(3)
                for i, skill in enumerate(sorted(skills)):
                    col_idx = i % 3
                    cols[col_idx].write(f"• {skill}")

def refine_search_candidates(query, current_filters):
    """Refine search based on new query and existing filters"""
    try:
        logger.info(f"Processing new search query: {query}")
        logger.info(f"Current filters before update: {json.dumps(current_filters, indent=2) if current_filters else 'None'}")
        
        # Extract new filters from the query
        new_filters = openai_client.extract_query_filters(query)
        logger.info(f"LLM extracted filters: {json.dumps(new_filters, indent=2)}")
        
        # Merge with existing filters
        if current_filters:
            # Update only the fields that are mentioned in the new query
            if new_filters['location']:
                current_filters['location'] = new_filters['location']
            if new_filters['experience_years_min']:
                current_filters['experience_years_min'] = new_filters['experience_years_min']
            if new_filters['required_skills']:
                current_filters['required_skills'] = new_filters['required_skills']
            if new_filters['role']:
                current_filters['role'] = new_filters['role']
        else:
            current_filters = new_filters
        
        logger.info(f"Final filters after merge: {json.dumps(current_filters, indent=2)}")
        
        # Build the query
        query = supabase.table('resumes').select(
            'id, full_name, location, total_years_experience, current_or_last_job_title, skills'
        )

        # Apply optional filters
        if current_filters.get('location'):
            query = query.ilike('location', f'%{current_filters["location"]}%')
        
        if current_filters.get('experience_years_min'):
            query = query.gte('total_years_experience', current_filters['experience_years_min'])

        # Initialize results list
        all_results = []

        # Get role matches
        if current_filters.get('role'):
            role_query = supabase.table('resumes').select(
                'id, full_name, location, total_years_experience, current_or_last_job_title, skills'
            )
            
            # Apply location and experience filters if present
            if current_filters.get('location'):
                role_query = role_query.ilike('location', f'%{current_filters["location"]}%')
            if current_filters.get('experience_years_min'):
                role_query = role_query.gte('total_years_experience', current_filters['experience_years_min'])
            
            # Add main role condition
            role_query = role_query.ilike('current_or_last_job_title', f'%{current_filters["role"]}%')
            role_results = role_query.execute()
            all_results.extend(role_results.data)
            
            # Add related roles
            if current_filters.get('related_roles'):
                for role in current_filters['related_roles']:
                    related_query = supabase.table('resumes').select(
                        'id, full_name, location, total_years_experience, current_or_last_job_title, skills'
                    )
                    # Apply location and experience filters if present
                    if current_filters.get('location'):
                        related_query = related_query.ilike('location', f'%{current_filters["location"]}%')
                    if current_filters.get('experience_years_min'):
                        related_query = related_query.gte('total_years_experience', current_filters['experience_years_min'])
                    
                    related_query = related_query.ilike('current_or_last_job_title', f'%{role}%')
                    related_results = related_query.execute()
                    all_results.extend(related_results.data)

        # Get skills matches
        if current_filters.get('required_skills'):
            for skill in current_filters['required_skills']:
                skill_query = supabase.table('resumes').select(
                    'id, full_name, location, total_years_experience, current_or_last_job_title, skills'
                )
                
                # Apply location and experience filters if present
                if current_filters.get('location'):
                    skill_query = skill_query.ilike('location', f'%{current_filters["location"]}%')
                if current_filters.get('experience_years_min'):
                    skill_query = skill_query.gte('total_years_experience', current_filters['experience_years_min'])
                
                skill_query = skill_query.contains('skills', [skill.upper()])
                skill_results = skill_query.execute()
                all_results.extend(skill_results.data)

        # Remove duplicates based on id
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result['id'] not in seen_ids:
                seen_ids.add(result['id'])
                unique_results.append(result)

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(unique_results)
        logger.info(f"Found {len(df)} unique candidates")
        
        # Log detailed matching information
        for _, candidate in df.iterrows():
            logger.info(f"\nCandidate: {candidate['full_name']}")
            logger.info(f"Location: {candidate['location']}")
            logger.info(f"Job Title: {candidate['current_or_last_job_title']}")
            logger.info(f"Experience: {candidate['total_years_experience']} years")
            logger.info(f"Skills: {candidate['skills']}")
            
            # Log which filters matched
            if current_filters.get('location'):
                logger.info(f"✓ Matched location: {current_filters['location']}")
            if current_filters.get('experience_years_min'):
                logger.info(f"✓ Matched experience: {current_filters['experience_years_min']}+ years")
            if current_filters.get('role'):
                logger.info(f"✓ Matched role: {current_filters['role']}")
            if current_filters.get('required_skills'):
                matched_skills = [skill for skill in current_filters['required_skills'] 
                               if skill.upper() in [s.upper() for s in candidate['skills']]]
                if matched_skills:
                    logger.info(f"✓ Matched skills: {matched_skills}")
        
        # Convert back to list of dictionaries
        candidates = df.to_dict('records')
        
        return candidates, current_filters
    except Exception as e:
        logger.error(f"Error searching candidates: {str(e)}", exc_info=True)
        return [], current_filters

def format_candidate_response(candidates):
    """Format candidate search results into a table"""
    if not candidates:
        return "I couldn't find any candidates matching your criteria."
    
    # Create a DataFrame for display
    df = pd.DataFrame(candidates)
    
    # Select and rename columns for display
    display_df = df[['full_name', 'skills', 'total_years_experience', 'location', 'current_or_last_job_title']]
    display_df.columns = ['Name', 'Skills', 'Experience (years)', 'Location', 'Current Job Title']
    
    # Format skills as comma-separated string
    display_df['Skills'] = display_df['Skills'].apply(lambda x: ', '.join(x) if isinstance(x, list) else x)
    
    # Display the table
    st.dataframe(
        display_df,
        column_config={
            "Name": st.column_config.TextColumn("Name", width="medium"),
            "Skills": st.column_config.TextColumn("Skills", width="large"),
            "Experience (years)": st.column_config.NumberColumn("Experience (years)", width="small"),
            "Location": st.column_config.TextColumn("Location", width="medium"),
            "Current Job Title": st.column_config.TextColumn("Current Job Title", width="large")
        },
        hide_index=True
    )
    
    return f"Found {len(candidates)} matching candidates."

def format_current_filters(filters):
    """Format current filters for display"""
    if not filters:
        return "No active filters"
    
    filter_parts = []
    if filters.get('role'):
        filter_parts.append(f"👤 Role: {filters['role']}")
    if filters.get('location'):
        filter_parts.append(f"📍 Location: {filters['location']}")
    if filters.get('experience_years_min'):
        filter_parts.append(f"⏳ Min Experience: {filters['experience_years_min']} years")
    if filters.get('required_skills'):
        filter_parts.append(f"🛠️ Skills: {', '.join(filters['required_skills'])}")
    
    return " | ".join(filter_parts)

def save_chat_message(question, answer):
    """Save chat message to Supabase"""
    try:
        if not st.session_state.user_email:
            st.warning("User email not found. Chat history will not be saved.")
            return
            
        data = {
            'user_email': st.session_state.user_email,
            'question': question,
            'answer': answer,
            'timestamp': datetime.now(UTC).isoformat()
        }
        
        response = supabase.table('chat_history').insert(data).execute()
        
        if hasattr(response, 'error') and response.error:
            st.error(f"Error saving chat message: {response.error}")
            return
            
    except Exception as e:
        st.error(f"Error saving chat message: {str(e)}")
        # Log the full error details for debugging
        print(f"Detailed error in save_chat_message: {str(e)}")
        print(f"Data attempted to save: {data}")

def load_chat_history():
    """Load chat history from Supabase and group by session"""
    try:
        if not st.session_state.user_email:
            return []
            
        response = supabase.table('chat_history')\
            .select('*')\
            .eq('user_email', st.session_state.user_email)\
            .order('timestamp', desc=True)\
            .limit(5)\
            .execute()
            
        if not response.data:
            return []
            
        # Group conversations by session (30-minute intervals)
        sessions = {}
        for chat in response.data:
            timestamp = datetime.fromisoformat(chat['timestamp'].replace('Z', '+00:00'))
            # Create session key based on 30-minute intervals
            session_key = timestamp.strftime('%Y-%m-%d %H:%M')
            if session_key not in sessions:
                sessions[session_key] = []
            sessions[session_key].append(chat)
            
        return sessions
    except Exception as e:
        st.error(f"Error loading chat history: {str(e)}")
        return {}

def display_chat_history(sessions):
    """Display chat history grouped by session"""
    if not sessions:
        st.info("No recent conversations found.")
        return
        
    st.markdown("#### Last 5 Conversations")
    for session_time, chats in sessions.items():
        # Convert session time to a more readable format
        session_dt = datetime.strptime(session_time, '%Y-%m-%d %H:%M')
        time_ago = datetime.now(UTC) - session_dt.replace(tzinfo=UTC)
        
        # Format the time ago string
        if time_ago.days > 0:
            time_str = f"{time_ago.days} days ago"
        elif time_ago.seconds >= 3600:
            hours = time_ago.seconds // 3600
            time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif time_ago.seconds >= 60:
            minutes = time_ago.seconds // 60
            time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            time_str = "just now"
            
        with st.expander(f"🗨️ Session from {time_str}", expanded=True):
            # Display each chat in the session
            for chat in chats:
                st.markdown("---")
                st.markdown("**Question:**")
                st.write(chat['question'])
                st.markdown("**Answer:**")
                st.write(chat['answer'])
                
                # Add a button to reuse the query
                if st.button("Reuse this search", key=f"reuse_{chat['id']}"):
                    st.session_state.last_query = chat['question']
                    # Execute the search immediately
                    with st.spinner("Searching for candidates..."):
                        candidates, updated_filters = refine_search_candidates(chat['question'], None)
                        st.session_state.search_results = candidates
                        st.session_state.current_filters = updated_filters
                        answer = format_candidate_response(candidates)
                        st.rerun()

def main():
    st.set_page_config(
        page_title="SkillQ - Chat",
        page_icon="💬",
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

    # Create two columns for layout
    col1, col2 = st.columns([2, 1])

    with col1:
        st.title("💬 Ask SkillQ")
        st.write("Ask me anything about candidate skills and experience!")

        # Chat input
        question = st.text_area(
            "Your question",
            placeholder="Example: Find me candidates with Python and React experience",
            height=100,
            value=st.session_state.last_query if st.session_state.last_query else ""
        )

        if st.button("Ask"):
            if question:
                with st.spinner("Searching for candidates..."):
                    # Search for candidates with context
                    candidates, updated_filters = refine_search_candidates(question, st.session_state.current_filters)
                    st.session_state.search_results = candidates
                    st.session_state.last_query = question
                    st.session_state.current_filters = updated_filters
                    answer = format_candidate_response(candidates)
                    
                    # Save to chat history
                    save_chat_message(question, answer)
                    
                    # Update session state
                    st.session_state.chat_history.insert(0, {
                        'question': question,
                        'answer': answer,
                        'timestamp': datetime.now(UTC).isoformat()
                    })
                    st.rerun()  # Rerun to update the filters display
            else:
                st.warning("Please enter a question")

        # Display current filters if any
        if st.session_state.current_filters:
            st.markdown("---")
            st.markdown("### 🔍 Active Search Filters")
            st.markdown(f"**{format_current_filters(st.session_state.current_filters)}**")
            st.markdown("---")

        # Display search results if available
        if st.session_state.search_results is not None:
            st.subheader("Search Results")
            if st.session_state.last_query:
                st.write(f"Results for: {st.session_state.last_query}")
            format_candidate_response(st.session_state.search_results)

    with col2:
        st.subheader("Available Skills")
        skills_by_category = get_candidate_skills()
        display_skills(skills_by_category)

        st.subheader("Recent Conversations")
        # Load and display chat history grouped by session
        sessions = load_chat_history()
        display_chat_history(sessions)

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.session_state.chat_history = []
        st.session_state.search_results = None
        st.session_state.last_query = None
        st.session_state.current_filters = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 