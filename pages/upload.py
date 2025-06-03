import streamlit as st
import os
from pathlib import Path
import sys
import logging
from functools import lru_cache
import time
import concurrent.futures
import multiprocessing
import gc

# Configure logging for console only with minimal overhead
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def get_session(key, default=None):
    """Helper function for lazy session state initialization"""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

# Lazy imports with minimal caching
@st.cache_resource(max_entries=5)  # Limit to 5 instances
def get_supabase_client():
    from backend.supabase_client import SupabaseClient
    return SupabaseClient()

@st.cache_resource(max_entries=5)  # Limit to 5 instances
def get_resume_processor():
    from backend.resume_processor import ResumeProcessor
    return ResumeProcessor()

# Initialize session state
def initialize_session_state():
    """Initialize only essential session state variables"""
    get_session('authenticated', False)
    get_session('user_email')
    get_session('user_id')

# Cache the file uploader component with minimal caching
@st.cache_data(ttl=300, max_entries=20)  # 5 minutes, max 20 entries
def get_file_uploader(label, file_type, key_base, multiple=False):
    """Helper function to create a file uploader with automatic reset capability"""
    return st.file_uploader(
        label,
        type=file_type,
        key=key_base,
        accept_multiple_files=multiple
    )

def file_uploader_with_reset(label, file_type, key_base, multiple=False):
    """Helper function to create a file uploader with automatic reset capability"""
    reset_key = f"reset_{key_base}"
    input_key = f"{key_base}_{int(time.time())}" if reset_key in st.session_state else key_base
    uploader = st.file_uploader(
        label,
        type=file_type,
        key=input_key,
        accept_multiple_files=multiple
    )
    if reset_key in st.session_state:
        del st.session_state[reset_key]
    return uploader

# Process files in chunks to save memory
def process_file_in_chunks(file_content, chunk_size=1024*1024):  # 1MB chunks
    """Process file content in chunks to save memory"""
    while True:
        chunk = file_content.read(chunk_size)
        if not chunk:
            break
        yield chunk

def process_single_upload(file_content, file_name, user_id):
    """Process a single file upload with memory-efficient processing"""
    max_retries = 3
    retry_count = 0
    
    logger.info(f"Starting to process file: {file_name}")
    
    while retry_count < max_retries:
        try:
            processor = get_resume_processor()
            
            # If file_content is already bytes, use it directly
            if isinstance(file_content, bytes):
                content = file_content
            else:
                # If it's a file-like object, read it once
                content = file_content.read()
            
            # Process content in parallel with progress updates
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Start the processing in a separate thread
                future = executor.submit(processor.process_resume_content, content, file_name)
                
                # Update progress while processing
                while not future.done():
                    time.sleep(0.1)
                
                result = future.result()
            
            # Clear content to free memory
            del content
            gc.collect()
            
            logger.info(f"Successfully processed file: {file_name}")
            return result
        except Exception as e:
            retry_count += 1
            error_msg = str(e)
            
            # Handle specific error cases
            if "400" in error_msg:
                st.error(f"Invalid resume format or content in {file_name}. Please ensure the file is a valid PDF or DOCX file.")
            elif "401" in error_msg or "403" in error_msg:
                st.error("Authentication error. Please try logging in again.")
            elif "413" in error_msg:
                st.error(f"File {file_name} is too large. Please upload a smaller file.")
            elif "500" in error_msg:
                st.error("Server error. Please try again later.")
            else:
                st.error(f"Error processing file {file_name} (attempt {retry_count}/{max_retries}): {error_msg}")
            
            logger.error(f"Error processing file {file_name} (attempt {retry_count}/{max_retries}): {error_msg}", exc_info=True)
            
            if retry_count == max_retries:
                return None
                
            st.warning(f"Retrying {file_name} (attempt {retry_count + 1}/{max_retries})...")
            # Implement exponential backoff for retries
            backoff_time = min(2 ** retry_count, 10)  # Cap at 10 seconds
            time.sleep(backoff_time)

def process_bulk_upload(uploaded_files):
    """Process multiple files in parallel with memory optimization"""
    batch_size = 3  # Reduced batch size for better memory management
    results = []
    total_files = len(uploaded_files)
    
    logger.info(f"Starting bulk upload of {total_files} files")
    
    # Get processor once for all batches
    processor = get_resume_processor()
    
    for i in range(0, total_files, batch_size):
        batch = uploaded_files[i:i + batch_size]
        current_batch = i // batch_size + 1
        total_batches = (total_files + batch_size - 1) // batch_size
        
        logger.debug(f"Processing batch {current_batch} of {total_batches}")
        
        # Dynamically set max_workers based on CPU count and available memory
        max_workers = min(len(batch), multiprocessing.cpu_count() // 2)  # Use half the CPU cores
        logger.debug(f"Using {max_workers} worker threads for batch processing")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    process_single_upload,
                    file.getvalue(),
                    file.name,
                    get_session('user_id')
                ): file 
                for file in batch
            }
            
            # Track progress within the batch
            completed = 0
            for future in concurrent.futures.as_completed(future_to_file):
                file = future_to_file[future]
                try:
                    result = future.result()
                    results.append((file.name, bool(result)))
                    completed += 1
                    logger.info(f"Successfully processed {file.name}")
                except Exception as e:
                    error_msg = str(e)
                    results.append((file.name, False))
                    
                    # Handle specific error cases
                    if "400" in error_msg:
                        st.error(f"Invalid resume format or content in {file.name}. Please ensure the file is a valid PDF or DOCX file.")
                    elif "401" in error_msg or "403" in error_msg:
                        st.error("Authentication error. Please try logging in again.")
                    elif "413" in error_msg:
                        st.error(f"File {file.name} is too large. Please upload a smaller file.")
                    elif "500" in error_msg:
                        st.error("Server error. Please try again later.")
                    else:
                        st.error(f"Error processing {file.name}: {error_msg}")
                    
                    logger.error(f"Error processing {file.name}: {error_msg}", exc_info=True)
        
        # Force garbage collection after each batch
        gc.collect()
    
    # Show completion
    success_count = sum(1 for _, success in results if success)
    logger.info(f"Bulk upload completed. Successfully processed {success_count} out of {total_files} files")
    return results

def main():
    st.set_page_config(
        page_title="SkillQ - Resume Upload",
        page_icon="📄",
        layout="wide"
    )
    
    initialize_session_state()
    
    # Check if user is authenticated
    if not get_session('authenticated'):
        st.warning("Please log in to access this page")
        return

    # Lazy load Supabase client without displaying loading message
    supabase_client = get_session('supabase_client')
    if supabase_client is None:
        st.session_state.supabase_client = get_supabase_client()

    # Add back button at the top
    if st.button("← Back to Home"):
        get_session('page', 'Home')
        st.switch_page("pages/home.py")

    st.title("📄 Resume Upload")
    st.write(f"Welcome, {get_session('user_email', 'User')}!")

    # Create two columns for single and bulk upload
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Single Upload")
        uploaded_file = file_uploader_with_reset(
            "Upload a resume",
            ['pdf', 'docx'],
            "single_upload"
        )
        
        if uploaded_file:
            if st.button("Process Single Upload"):
                with st.spinner("Processing resume..."):
                    result = process_single_upload(
                        uploaded_file.getvalue(),
                        uploaded_file.name,
                        get_session('user_id')
                    )
                    if result:
                        st.success(f"Successfully processed {uploaded_file.name}!")
                        # Set reset flag for the uploader
                        get_session('reset_single_upload', True)
                        st.rerun()

    with col2:
        st.subheader("Bulk Upload")
        uploaded_files = file_uploader_with_reset(
            "Upload multiple resumes",
            ['pdf', 'docx'],
            "bulk_upload",
            multiple=True
        )
        
        if uploaded_files:
            if st.button("Process Bulk Upload"):
                with st.spinner("Processing resumes..."):
                    results = process_bulk_upload(uploaded_files)
                    success_count = sum(1 for _, success in results if success)
                    
                    st.success(f"Successfully processed {success_count} out of {len(uploaded_files)} files")
                    
                    # Show failed files if any
                    failed_files = [name for name, success in results if not success]
                    if failed_files:
                        st.warning(f"Failed to process: {', '.join(failed_files)}")
                    
                    # Set reset flag for the uploader
                    get_session('reset_bulk_upload', True)
                    st.rerun()

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        get_session('authenticated', False)
        get_session('user_email', None)
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 