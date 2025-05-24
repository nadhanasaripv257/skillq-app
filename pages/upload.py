import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import tempfile
import shutil
from pathlib import Path
import PyPDF2
import docx
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

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return None

def extract_text_from_docx(file_path):
    """Extract text from DOCX file"""
    try:
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return None

def extract_skills(text):
    """Extract skills from text (placeholder function - to be enhanced with NLP)"""
    # This is a placeholder. In a real application, you would use NLP or ML to extract skills
    # For now, we'll just return some dummy data
    return {
        "skills": ["Python", "JavaScript", "React", "Node.js", "SQL"],
        "confidence": 0.85
    }

def save_to_supabase(file_name, file_type, text_content, skills_data, user_email):
    """Save resume data to Supabase"""
    try:
        data = {
            "file_name": file_name,
            "file_type": file_type,
            "content": text_content,
            "skills": json.dumps(skills_data),
            "uploaded_by": user_email,
            "uploaded_at": datetime.utcnow().isoformat()
        }
        
        response = supabase.table('resumes').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error saving to database: {str(e)}")
        return False

def process_single_upload(uploaded_file, user_email):
    """Process a single file upload"""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
        shutil.copyfileobj(uploaded_file, tmp_file)
        tmp_file_path = tmp_file.name

    try:
        # Extract text based on file type
        if uploaded_file.name.lower().endswith('.pdf'):
            text_content = extract_text_from_pdf(tmp_file_path)
        elif uploaded_file.name.lower().endswith('.docx'):
            text_content = extract_text_from_docx(tmp_file_path)
        else:
            st.error("Unsupported file format")
            return False

        if text_content:
            # Extract skills from text
            skills_data = extract_skills(text_content)
            
            # Save to Supabase
            if save_to_supabase(
                uploaded_file.name,
                os.path.splitext(uploaded_file.name)[1][1:],
                text_content,
                skills_data,
                user_email
            ):
                st.success(f"Successfully processed {uploaded_file.name}")
                return True
    finally:
        # Clean up temporary file
        os.unlink(tmp_file_path)
    
    return False

def main():
    st.set_page_config(
        page_title="SkillQ - Resume Upload",
        page_icon="📄",
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

    st.title("📄 Resume Upload")
    st.write(f"Welcome, {st.session_state.user_email}!")

    # Create two columns for single and bulk upload
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Single Upload")
        uploaded_file = st.file_uploader(
            "Upload a resume",
            type=['pdf', 'docx'],
            help="Upload a single PDF or DOCX file"
        )
        
        if uploaded_file:
            if st.button("Process Single Upload"):
                with st.spinner("Processing..."):
                    if process_single_upload(uploaded_file, st.session_state.user_email):
                        st.success("Upload completed successfully!")

    with col2:
        st.subheader("Bulk Upload")
        uploaded_files = st.file_uploader(
            "Upload multiple resumes",
            type=['pdf', 'docx'],
            accept_multiple_files=True,
            help="Upload multiple PDF or DOCX files"
        )
        
        if uploaded_files:
            if st.button("Process Bulk Upload"):
                with st.spinner("Processing..."):
                    success_count = 0
                    for uploaded_file in uploaded_files:
                        if process_single_upload(uploaded_file, st.session_state.user_email):
                            success_count += 1
                    
                    st.success(f"Successfully processed {success_count} out of {len(uploaded_files)} files")

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("login.py")

if __name__ == "__main__":
    main() 