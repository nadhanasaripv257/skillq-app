import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import json
from datetime import datetime

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
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

def get_candidate_skills():
    """Get all candidate skills from resumes"""
    try:
        response = supabase.table('resumes').select('skills').execute()
        all_skills = set()
        for resume in response.data:
            skills_data = json.loads(resume['skills'])
            all_skills.update(skills_data['skills'])
        return sorted(list(all_skills))
    except Exception as e:
        st.error(f"Error loading skills: {str(e)}")
        return []

def search_candidates(query):
    """Search for candidates based on query"""
    try:
        # Get all resumes
        response = supabase.table('resumes').select('*').execute()
        
        # Simple keyword matching for now
        # TODO: Implement more sophisticated search using NLP
        matching_candidates = []
        for resume in response.data:
            skills_data = json.loads(resume['skills'])
            if any(skill.lower() in query.lower() for skill in skills_data['skills']):
                matching_candidates.append({
                    'file_name': resume['file_name'],
                    'skills': skills_data['skills'],
                    'confidence': skills_data['confidence']
                })
        
        return matching_candidates
    except Exception as e:
        st.error(f"Error searching candidates: {str(e)}")
        return []

def format_candidate_response(candidates):
    """Format candidate search results into a readable response"""
    if not candidates:
        return "I couldn't find any candidates matching your criteria."
    
    response = "Here are the matching candidates:\n\n"
    for i, candidate in enumerate(candidates, 1):
        response += f"{i}. {candidate['file_name']}\n"
        response += f"   Skills: {', '.join(candidate['skills'])}\n"
        response += f"   Match Confidence: {candidate['confidence']*100:.1f}%\n\n"
    
    return response

def save_chat_message(question, answer):
    """Save chat message to Supabase"""
    try:
        data = {
            'user_email': st.session_state.user_email,
            'question': question,
            'answer': answer,
            'timestamp': datetime.utcnow().isoformat()
        }
        supabase.table('chat_history').insert(data).execute()
    except Exception as e:
        st.error(f"Error saving chat message: {str(e)}")

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
            height=100
        )

        if st.button("Ask"):
            if question:
                with st.spinner("Searching for candidates..."):
                    # Search for candidates
                    candidates = search_candidates(question)
                    answer = format_candidate_response(candidates)
                    
                    # Save to chat history
                    save_chat_message(question, answer)
                    
                    # Update session state
                    st.session_state.chat_history.insert(0, {
                        'question': question,
                        'answer': answer,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    
                    st.rerun()
            else:
                st.warning("Please enter a question")

    with col2:
        st.subheader("Available Skills")
        skills = get_candidate_skills()
        if skills:
            st.write("Here are some skills you can ask about:")
            st.write(", ".join(skills))
        else:
            st.info("No skills found. Please upload some resumes first.")

        st.subheader("Recent Conversations")
        for chat in st.session_state.chat_history:
            with st.expander(f"Q: {chat['question'][:50]}..."):
                st.write("**Question:**")
                st.write(chat['question'])
                st.write("**Answer:**")
                st.write(chat['answer'])

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.session_state.chat_history = []
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 