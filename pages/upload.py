import streamlit as st
import os
from pathlib import Path
import sys
import logging
from functools import lru_cache
import time
import concurrent.futures
import multiprocessing

# Configure logging for console only
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def get_session(key, default=None):
    """Helper function for lazy session state initialization"""
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

# Lazy imports with caching
@st.cache_resource
def get_supabase_client():
    from backend.supabase_client import SupabaseClient
    return SupabaseClient()

@st.cache_resource
def get_resume_processor():
    from backend.resume_processor import ResumeProcessor
    return ResumeProcessor()

# Initialize session state
def initialize_session_state():
    """Initialize only essential session state variables"""
    get_session('authenticated', False)
    get_session('user_email')
    get_session('user_id')

# Cache the file uploader component with a shorter TTL
@st.cache_data(ttl=300)  # Cache for 5 minutes since file uploaders don't need long caching
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

# Cache processed files with a shorter TTL and max size limit
@st.cache_data(ttl=1800, max_entries=100)  # Cache for 30 minutes, max 100 entries
def process_single_upload(file_content, file_name, user_id):
    """Process a single file upload with caching and error recovery"""
    max_retries = 3
    retry_count = 0
    
    logger.info(f"Starting to process file: {file_name}")
    
    # Create a progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    while retry_count < max_retries:
        try:
            processor = get_resume_processor()
            
            # Update progress for each step
            status_text.text("Reading file...")
            progress_bar.progress(25)
            
            # Process content in parallel with progress updates
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # Start the processing in a separate thread
                future = executor.submit(processor.process_resume_content, file_content, file_name)
                
                # Update progress while processing
                while not future.done():
                    status_text.text("Processing content...")
                    progress_bar.progress(50)
                    time.sleep(0.1)  # Reduced delay for smoother progress
                
                result = future.result()
            
            status_text.text("Storing data...")
            progress_bar.progress(75)
            
            status_text.text("Complete!")
            progress_bar.progress(100)
            
            logger.info(f"Successfully processed file: {file_name}")
            return result
        except Exception as e:
            retry_count += 1
            logger.error(f"Error processing file {file_name} (attempt {retry_count}/{max_retries}): {str(e)}", exc_info=True)
            if retry_count == max_retries:
                st.error(f"Error processing file {file_name} after {max_retries} attempts: {str(e)}")
                return None
            st.warning(f"Retrying {file_name} (attempt {retry_count + 1}/{max_retries})...")
            # Implement exponential backoff for retries
            backoff_time = min(2 ** retry_count, 10)  # Cap at 10 seconds
            time.sleep(backoff_time)

# No caching for bulk upload as it's a one-time operation
def process_bulk_upload(uploaded_files):
    """Process multiple files in parallel with batch processing and memory optimization"""
    batch_size = 5  # Reduced batch size for better memory management
    results = []
    total_files = len(uploaded_files)
    
    logger.info(f"Starting bulk upload of {total_files} files")
    
    # Create a progress bar for overall progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(f"Starting upload of {total_files} files...")
    
    # Get processor once for all batches
    processor = get_resume_processor()
    
    for i in range(0, total_files, batch_size):
        batch = uploaded_files[i:i + batch_size]
        current_batch = i // batch_size + 1
        total_batches = (total_files + batch_size - 1) // batch_size
        
        logger.debug(f"Processing batch {current_batch} of {total_batches}")
        status_text.text(f"Processing batch {current_batch} of {total_batches}...")
        
        # Dynamically set max_workers based on CPU count and available memory
        max_workers = min(len(batch), multiprocessing.cpu_count())  # Reduced worker count for better stability
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
                    # Update progress within batch
                    batch_progress = completed / len(batch)
                    overall_progress = (i + completed) / total_files
                    progress_bar.progress(overall_progress)
                    status_text.text(f"Processing batch {current_batch} of {total_batches}... ({completed}/{len(batch)} files)")
                    logger.info(f"Successfully processed {file.name}")
                except Exception as e:
                    results.append((file.name, False))
                    logger.error(f"Error processing {file.name}: {str(e)}", exc_info=True)
                    st.error(f"Error processing {file.name}: {str(e)}")
        
        # Update overall progress after batch completion
        progress = min(1.0, (i + len(batch)) / total_files)
        status_text.text(f"Completed batch {current_batch} of {total_batches}")
        progress_bar.progress(progress)
    
    # Show completion
    success_count = sum(1 for _, success in results if success)
    status_text.text(f"Upload complete! Successfully processed {success_count} out of {total_files} files")
    progress_bar.progress(1.0)
    
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

    # Lazy load Supabase client
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
                result = process_single_upload(
                    uploaded_file.getvalue(),
                    uploaded_file.name,
                    get_session('user_id')
                )
                if result:
                    # Store success message in session state
                    get_session('upload_success', f"Successfully processed {uploaded_file.name}!")
                    st.success(get_session('upload_success'))
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
                results = process_bulk_upload(uploaded_files)
                success_count = sum(1 for _, success in results if success)
                
                # Store success message in session state
                get_session('bulk_upload_success', f"Successfully processed {success_count} out of {len(uploaded_files)} files")
                st.success(get_session('bulk_upload_success'))
                
                # Show failed files if any
                failed_files = [name for name, success in results if not success]
                if failed_files:
                    st.warning(f"Failed to process: {', '.join(failed_files)}")
                
                # Set reset flag for the uploader
                get_session('reset_bulk_upload', True)
                st.rerun()

    # Display any stored success messages
    upload_success = get_session('upload_success')
    if upload_success:
        st.success(upload_success)
        # Clear the message after displaying
        del st.session_state.upload_success
    
    bulk_upload_success = get_session('bulk_upload_success')
    if bulk_upload_success:
        st.success(bulk_upload_success)
        # Clear the message after displaying
        del st.session_state.bulk_upload_success

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        get_session('authenticated', False)
        get_session('user_email', None)
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 