import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import json
from datetime import datetime, UTC
from backend.openai_client import OpenAIClient
from backend.supabase_client import SupabaseClient
import pandas as pd
import logging
import time
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_client = SupabaseClient()

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
    if 'last_outreach_time' not in st.session_state:
        st.session_state.last_outreach_time = {}
    if 'outreach_count' not in st.session_state:
        st.session_state.outreach_count = {}
    if 'trigger_search' not in st.session_state:
        st.session_state.trigger_search = False

def get_candidate_skills():
    """Get all candidate skills from resumes and organize them by category"""
    try:
        response = supabase_client.table('resumes').select('skills, skill_categories').execute()
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
        
        # Extract new filters from the query first
        new_filters = openai_client.extract_query_filters(query)
        logger.info(f"LLM extracted filters: {json.dumps(new_filters, indent=2)}")
        
        # Replace current filters with new filters instead of merging
        current_filters = new_filters
        
        logger.info(f"Final filters after update: {json.dumps(current_filters, indent=2)}")
        
        # Get all keywords from filters
        keywords = []
        if current_filters.get('role'):
            keywords.append(current_filters['role'].lower())
        if current_filters.get('related_roles'):
            keywords.extend([role.lower() for role in current_filters['related_roles']])
        if current_filters.get('required_skills'):
            keywords.extend([skill.lower() for skill in current_filters['required_skills']])

        # Initialize set to store matched candidate IDs
        matched_ids = set()

        # First, search by keywords if any
        if keywords:
            for keyword in keywords:
                # Build base query
                keyword_query = supabase_client.table('resumes').select('id')
                
                # Add keyword search condition
                if len(keyword) >= 3:
                    # Allow partial matches for keywords >= 3 chars
                    keyword_query = keyword_query.ilike('search_blob', f'%{keyword}%')
                else:
                    # Only exact matches for short keywords
                    keyword_query = keyword_query.ilike('search_blob', f'%|{keyword}|%')
                
                # Execute query and collect IDs
                response = keyword_query.execute()
                for result in response.data:
                    matched_ids.add(result['id'])
        else:
            # If no keywords, get all candidates
            response = supabase_client.table('resumes').select('id').execute()
            for result in response.data:
                matched_ids.add(result['id'])

        # Fetch full details for matched candidates
        final_candidates = []
        if matched_ids:
            for candidate_id in matched_ids:
                response = supabase_client.table('resumes')\
                    .select('id, full_name, location, total_years_experience, current_or_last_job_title, skills, search_blob, risk_score, issues')\
                    .eq('id', candidate_id)\
                    .execute()
                if response.data:
                    candidate = response.data[0]
                    
                    # Apply location filter if present
                    if current_filters.get('location'):
                        if not candidate['location'] or current_filters['location'].lower() not in candidate['location'].lower():
                            continue
                    
                    # Apply experience filter if present
                    if current_filters.get('experience_years_min'):
                        if not candidate['total_years_experience'] or candidate['total_years_experience'] < current_filters['experience_years_min']:
                            continue
                    
                    final_candidates.append(candidate)

        # Convert to DataFrame for easier manipulation
        df = pd.DataFrame(final_candidates)
        logger.info(f"Found {len(df)} unique candidates")
        
        # Return early if no candidates found
        if len(df) == 0:
            logger.info("No matching candidates found")
            return [], current_filters
        
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
            if keywords:
                # Check for partial matches in the pipe-separated list
                candidate_keywords = candidate['search_blob'].split('|')
                matched_keywords = []
                for kw in keywords:
                    # For keywords >= 3 chars, allow partial matches
                    if len(kw) >= 3:
                        if any(kw in word for word in candidate_keywords):
                            matched_keywords.append(kw)
                    # For shorter keywords, only match exact words
                    else:
                        if kw in candidate_keywords:
                            matched_keywords.append(kw)
                if matched_keywords:
                    logger.info(f"✓ Matched keywords: {matched_keywords}")
        
        # Convert back to list of dictionaries
        candidates = df.to_dict('records')
        
        return candidates, current_filters
    except Exception as e:
        logger.error(f"Error searching candidates: {str(e)}", exc_info=True)
        return [], current_filters

def can_generate_outreach(candidate_id: str) -> bool:
    """Check if we can generate outreach for this candidate based on rate limiting"""
    current_time = time.time()
    last_time = st.session_state.last_outreach_time.get(candidate_id, 0)
    count = st.session_state.outreach_count.get(candidate_id, 0)
    
    # Reset count if more than 1 hour has passed
    if current_time - last_time > 3600:
        st.session_state.outreach_count[candidate_id] = 0
        return True
    
    # Allow max 5 requests per hour
    if count >= 5:
        return False
    
    return True

def update_outreach_count(candidate_id: str):
    """Update the outreach count for rate limiting"""
    current_time = time.time()
    st.session_state.last_outreach_time[candidate_id] = current_time
    st.session_state.outreach_count[candidate_id] = st.session_state.outreach_count.get(candidate_id, 0) + 1

def format_candidate_response(candidates):
    """Format candidate search results into a table with rankings"""
    if not candidates:
        st.error("❌ No matching candidates found for your search criteria.")
        st.info("Try adjusting your search criteria or filters to find more candidates.")
        return "No matching candidates found."
    
    # Get ranked candidates
    ranked_candidates = openai_client.rank_candidates(
        st.session_state.last_query,
        candidates
    )
    
    # Display ranked results
    st.markdown("### 🏆 Ranked Candidates")
    
    for idx, ranked in enumerate(ranked_candidates, 1):
        candidate = ranked['candidate']
        
        # Create an expander for each candidate
        with st.expander(f"#{idx} {candidate['full_name']} - Score: {ranked['score']}/10", expanded=True):
            # Display candidate details
            st.markdown(f"**Current Role:** {candidate['current_or_last_job_title']}")
            st.markdown(f"**Experience:** {candidate['total_years_experience']} years")
            st.markdown(f"**Location:** {candidate['location']}")
            st.markdown("**Skills:**")
            st.markdown(", ".join(candidate['skills']))
            
            if 'education' in candidate and candidate['education']:
                st.markdown("**Education:**")
                st.markdown(", ".join(candidate['education']))
            
            # Add risk score and issues display
            if 'risk_score' in candidate and candidate['risk_score']:
                st.markdown("**Risk Score:**")
                st.markdown(f"⚠️ {candidate['risk_score']}")
            
            if 'issues' in candidate and candidate['issues']:
                st.markdown("**Issues:**")
                st.markdown(f"🚨 {candidate['issues']}")
            
            st.markdown("**Match Reasoning:**")
            for reason in ranked['reasoning']:
                st.markdown(f"• {reason}")
            
            # Add Generate Outreach button
            outreach_key = f"outreach_{candidate['id']}"
            if outreach_key not in st.session_state:
                st.session_state[outreach_key] = None
            
            if st.button("✉️ Generate Outreach & Questions", key=f"generate_outreach_{candidate['id']}"):
                if not can_generate_outreach(candidate['id']):
                    st.error("Rate limit exceeded. Please try again in an hour.")
                    continue
                
                with st.spinner("Generating personalized outreach..."):
                    # Get user ID from session
                    user_response = supabase_client.auth.get_user()
                    if not user_response.user:
                        st.error("Please log in to generate outreach messages")
                        continue
                    
                    recruiter_id = user_response.user.id
                    
                    # Check Supabase cache first
                    cached_data = supabase_client.get_cached_outreach(
                        candidate['id'],
                        st.session_state.last_query
                    )
                    
                    if cached_data:
                        outreach_data = cached_data
                    else:
                        # Generate new outreach data
                        outreach_data = openai_client.generate_outreach(
                            candidate=candidate,
                            original_query=st.session_state.last_query
                        )
                        # Cache the result
                        supabase_client.cache_outreach_message(
                            candidate['id'],
                            st.session_state.last_query,
                            outreach_data
                        )
                        update_outreach_count(candidate['id'])
                    
                    # Store in session state for persistence
                    st.session_state[outreach_key] = outreach_data
                    
                    # Force a rerun to update the UI
                    st.rerun()
            
            # Display outreach form if we have data
            if st.session_state[outreach_key]:
                outreach_data = st.session_state[outreach_key]
                
                st.markdown("### 📝 Outreach Message")
                outreach_message = st.text_area(
                    "Edit the message if needed:",
                    value=outreach_data['outreach_message'],
                    height=150,
                    key=f"outreach_text_{candidate['id']}"
                )
                
                st.markdown("### ❓ Screening Questions")
                questions = []
                for i, question in enumerate(outreach_data['screening_questions'], 1):
                    edited_question = st.text_input(
                        f"Question {i}:",
                        value=question,
                        key=f"question_{candidate['id']}_{i}"
                    )
                    questions.append(edited_question)
                
                # Add save button
                if st.button("💾 Save Draft", key=f"save_draft_{candidate['id']}"):
                    try:
                        # Get user ID from session
                        user_response = supabase_client.auth.get_user()
                        if not user_response.user:
                            st.error("Please log in to save drafts")
                            return
                        
                        recruiter_id = user_response.user.id
                        
                        # Save to Supabase
                        data = {
                            'id': str(uuid.uuid4()),  # Add generated UUID
                            'recruiter_id': recruiter_id,
                            'candidate_id': candidate['id'],
                            'outreach_message': outreach_message,
                            'screening_questions': questions
                        }
                        
                        response = supabase_client.table('recruiter_notes').insert(data).execute()
                        
                        if hasattr(response, 'error') and response.error:
                            st.error(f"Error saving draft: {response.error}")
                        else:
                            st.success("Draft saved successfully!")
                            
                    except Exception as e:
                        st.error(f"Error saving draft: {str(e)}")
            
            # Add a button to view full profile
            if st.button("View Full Profile", key=f"view_profile_{candidate['id']}"):
                display_candidate_profile(candidate)
    
    return f"Found and ranked {len(ranked_candidates)} matching candidates."

def display_candidate_profile(candidate):
    """Display detailed candidate profile in a modal"""
    st.markdown("### 📋 Full Candidate Profile")
    
    # Create two columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Personal Information")
        st.markdown(f"**Name:** {candidate['full_name']}")
        st.markdown(f"**Location:** {candidate['location']}")
        if 'email' in candidate:
            st.markdown(f"**Email:** {candidate['email']}")
        if 'phone' in candidate:
            st.markdown(f"**Phone:** {candidate['phone']}")
        if 'linkedin_url' in candidate:
            st.markdown(f"**LinkedIn:** {candidate['linkedin_url']}")
    
    with col2:
        st.markdown("#### Professional Information")
        st.markdown(f"**Current Role:** {candidate['current_or_last_job_title']}")
        st.markdown(f"**Experience:** {candidate['total_years_experience']} years")
        if 'employment_type' in candidate:
            st.markdown(f"**Employment Type:** {candidate['employment_type']}")
        if 'availability' in candidate:
            st.markdown(f"**Availability:** {candidate['availability']}")
    
    # Skills and Tools
    st.markdown("#### Skills & Tools")
    if 'skills' in candidate:
        st.markdown("**Skills:**")
        st.markdown(", ".join(candidate['skills']))
    if 'tools_technologies' in candidate:
        st.markdown("**Tools & Technologies:**")
        st.markdown(", ".join(candidate['tools_technologies']))
    
    # Education and Certifications
    st.markdown("#### Education & Certifications")
    if 'education' in candidate:
        st.markdown("**Education:**")
        st.markdown(", ".join(candidate['education']))
    if 'certifications' in candidate:
        st.markdown("**Certifications:**")
        st.markdown(", ".join(candidate['certifications']))
    
    # Additional Information
    if 'summary_statement' in candidate:
        st.markdown("#### Summary")
        st.markdown(candidate['summary_statement'])
    
    if 'languages_spoken' in candidate:
        st.markdown("#### Languages")
        st.markdown(", ".join(candidate['languages_spoken']))

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
        
        response = supabase_client.table('chat_history').insert(data).execute()
        
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
            
        response = supabase_client.table('chat_history')\
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
        
    # Create a list of all queries with their timestamps
    all_queries = []
    for session_time, chats in sessions.items():
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
            
        for chat in chats:
            all_queries.append({
                'question': chat['question'],
                'time': time_str,
                'answer': chat['answer']
            })
    
    # Display the queries in an expander
    with st.expander("🗨️ Last 5 Conversations", expanded=True):
        if all_queries:
            # Create radio options with timestamps
            radio_options = [f"{q['question']} ({q['time']})" for q in all_queries]
            selected_option = st.radio(
                "Select a previous question to reuse:",
                radio_options,
                label_visibility="collapsed"
            )
            
            # Get the selected query
            selected_query = all_queries[radio_options.index(selected_option)]['question']
            
            # Show preview of the selected query's results
            st.markdown("**Preview of previous results:**")
            st.write(all_queries[radio_options.index(selected_option)]['answer'])
            
            # Add a prominent reuse button
            if st.button("🔄 Run This Search", use_container_width=True):
                st.session_state.last_query = selected_query
                st.session_state.trigger_search = True
                st.rerun()
        else:
            st.info("No previous conversations found.")

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

        # Unified search trigger logic
        triggered = st.button("Ask") or st.session_state.get("trigger_search", False)

        if triggered:
            if question:
                with st.spinner("Searching for candidates..."):
                    candidates, updated_filters = refine_search_candidates(question, st.session_state.current_filters)
                    st.session_state.search_results = candidates
                    st.session_state.last_query = question
                    st.session_state.current_filters = updated_filters
                    answer = format_candidate_response(candidates)
                    save_chat_message(question, answer)
                    st.session_state.chat_history.insert(0, {
                        'question': question,
                        'answer': answer,
                        'timestamp': datetime.now(UTC).isoformat()
                    })
                    st.session_state.trigger_search = False  # Reset flag
                    st.rerun()
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
        st.session_state.trigger_search = False
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 