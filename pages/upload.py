import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
import tempfile
import shutil
from pathlib import Path
import json
from datetime import datetime
import sys
import concurrent.futures
from functools import lru_cache

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.resume_processor import ResumeProcessor
from backend.supabase_client import SupabaseClient

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase_client = SupabaseClient()

# Initialize ResumeProcessor with caching
@st.cache_resource
def get_resume_processor():
    return ResumeProcessor()

def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None

def process_single_upload(uploaded_file, user_id):
    """Process a single file upload"""
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name

        try:
            # Process the resume
            processor = get_resume_processor()
            result = processor.process_resume(tmp_file_path)
            return result
            
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return None

def process_bulk_upload(uploaded_files):
    """Process multiple files in parallel"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all files for processing
        future_to_file = {
            executor.submit(process_single_upload, file): file 
            for file in uploaded_files
        }
        
        # Process results as they complete
        results = []
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result:
                    results.append((file.name, True))
                else:
                    results.append((file.name, False))
            except Exception as e:
                results.append((file.name, False))
                st.error(f"Error processing {file.name}: {str(e)}")
        
        return results

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
            st.switch_page("pages/login.py")
        return

    # Add back button at the top
    if st.button("← Back to Home"):
        st.switch_page("app.py")

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
                with st.spinner("Processing resume..."):
                    result = process_single_upload(uploaded_file, st.session_state.user_id)
                    if result:
                        st.success(f"Successfully processed {uploaded_file.name}!")
                        if st.button("Upload Another Resume"):
                            st.rerun()

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
                with st.spinner("Processing multiple files..."):
                    results = process_bulk_upload(uploaded_files)
                    success_count = sum(1 for _, success in results if success)
                    
                    # Show detailed results
                    st.success(f"Successfully processed {success_count} out of {len(uploaded_files)} files")
                    
                    # Show failed files if any
                    failed_files = [name for name, success in results if not success]
                    if failed_files:
                        st.warning(f"Failed to process: {', '.join(failed_files)}")
                    
                    if st.button("Upload More Resumes"):
                        st.rerun()

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 