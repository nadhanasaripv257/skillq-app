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
import hashlib
import time

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

def get_file_hash(file_content):
    """Generate a hash of the file content for caching"""
    return hashlib.md5(file_content).hexdigest()

@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour, hide spinner
def process_single_upload(file_content, file_name, user_id):
    """Process a single file upload with caching and error recovery"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            processor = get_resume_processor()
            
            # Create a progress bar
            progress_bar = st.progress(0)
            
            # Update progress for each step
            progress_bar.progress(0.2, "Reading file...")
            progress_bar.progress(0.4, "Processing content...")
            result = processor.process_resume_content(file_content, file_name)
            progress_bar.progress(0.8, "Storing data...")
            progress_bar.progress(1.0, "Complete!")
            
            # Keep progress bar visible
            time.sleep(1)
            return result
        except Exception as e:
            retry_count += 1
            if retry_count == max_retries:
                st.error(f"Error processing file {file_name} after {max_retries} attempts: {str(e)}")
                return None
            st.warning(f"Retrying {file_name} (attempt {retry_count + 1}/{max_retries})...")
            time.sleep(1)  # Wait before retrying

def process_bulk_upload(uploaded_files):
    """Process multiple files in parallel with batch processing and memory optimization"""
    batch_size = 5  # Process 5 files at a time
    results = []
    total_files = len(uploaded_files)
    
    # Create a progress bar for overall progress
    progress_bar = st.progress(0)
    
    for i in range(0, total_files, batch_size):
        batch = uploaded_files[i:i + batch_size]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_file = {
                executor.submit(
                    process_single_upload,
                    file.getvalue(),
                    file.name,
                    st.session_state.user_id
                ): file 
                for file in batch
            }
            
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    result = future.result()
                    results.append((file.name, bool(result)))
                except Exception as e:
                    results.append((file.name, False))
                    st.error(f"Error processing {file.name}: {str(e)}")
        
        # Update overall progress
        progress = min(1.0, (i + batch_size) / total_files)
        progress_bar.progress(progress, f"Processing files... ({i + len(batch)}/{total_files})")
    
    # Show completion
    progress_bar.progress(1.0, "Complete!")
    time.sleep(1)
    
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
            help="Upload a single PDF or DOCX file",
            key="single_upload"
        )
        
        if uploaded_file:
            if st.button("Process Single Upload"):
                result = process_single_upload(
                    uploaded_file.getvalue(),
                    uploaded_file.name,
                    st.session_state.user_id
                )
                if result:
                    st.success(f"Successfully processed {uploaded_file.name}!")
                    if st.button("Upload Another Resume"):
                        st.session_state.single_upload = None
                        st.rerun()

    with col2:
        st.subheader("Bulk Upload")
        uploaded_files = st.file_uploader(
            "Upload multiple resumes",
            type=['pdf', 'docx'],
            accept_multiple_files=True,
            help="Upload multiple PDF or DOCX files",
            key="bulk_upload"
        )
        
        if uploaded_files:
            if st.button("Process Bulk Upload"):
                results = process_bulk_upload(uploaded_files)
                success_count = sum(1 for _, success in results if success)
                
                # Show success message
                st.success(f"Successfully processed {success_count} out of {len(uploaded_files)} files")
                
                # Show failed files if any
                failed_files = [name for name, success in results if not success]
                if failed_files:
                    st.warning(f"Failed to process: {', '.join(failed_files)}")
                
                if st.button("Upload More Resumes"):
                    st.session_state.bulk_upload = None
                    st.rerun()

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 