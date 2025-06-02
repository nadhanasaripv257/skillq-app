import streamlit as st
import os
from pathlib import Path
import sys
import logging
from functools import lru_cache

# Configure logging only if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,  # Changed to INFO to reduce logging overhead
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('resume_upload.log'),
            logging.StreamHandler()
        ]
    )
logger = logging.getLogger(__name__)

# Add backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Lazy imports
def get_supabase_client():
    from backend.supabase_client import SupabaseClient
    return SupabaseClient()

def get_resume_processor():
    from backend.resume_processor import ResumeProcessor
    return ResumeProcessor()

# Initialize session state
def initialize_session_state():
    """Initialize session state variables"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'upload_key' not in st.session_state:
        st.session_state.upload_key = 0
    if 'bulk_upload_key' not in st.session_state:
        st.session_state.bulk_upload_key = 0
    if 'supabase_client' not in st.session_state:
        st.session_state.supabase_client = None
    if 'resume_processor' not in st.session_state:
        st.session_state.resume_processor = None

# Cache the file uploader component
@st.cache_data(ttl=3600)  # Cache for 1 hour
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

def process_bulk_upload(uploaded_files):
    """Process multiple files in parallel with batch processing and memory optimization"""
    batch_size = 10  # Increased batch size for better throughput
    results = []
    total_files = len(uploaded_files)
    
    logger.info(f"Starting bulk upload of {total_files} files")
    
    # Create a progress bar for overall progress
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text(f"Starting upload of {total_files} files...")
    
    for i in range(0, total_files, batch_size):
        batch = uploaded_files[i:i + batch_size]
        current_batch = i // batch_size + 1
        total_batches = (total_files + batch_size - 1) // batch_size
        
        logger.debug(f"Processing batch {current_batch} of {total_batches}")
        status_text.text(f"Processing batch {current_batch} of {total_batches}...")
        
        # Dynamically set max_workers based on CPU count and available memory
        max_workers = min(len(batch), multiprocessing.cpu_count() * 2)  # Increased worker count
        logger.debug(f"Using {max_workers} worker threads for batch processing")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(
                    process_single_upload,
                    file.getvalue(),
                    file.name,
                    st.session_state.get('user_id')
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
    if not st.session_state.get('authenticated', False):
        st.warning("Please log in to access this page")
        return

    # Lazy load Supabase client
    if st.session_state.supabase_client is None:
        with st.spinner("Initializing..."):
            st.session_state.supabase_client = get_supabase_client()

    # Lazy load ResumeProcessor
    if st.session_state.resume_processor is None:
        with st.spinner("Loading processor..."):
            st.session_state.resume_processor = get_resume_processor()

    # Add back button at the top
    if st.button("← Back to Home"):
        st.session_state.page = "Home"
        st.switch_page("pages/home.py")

    st.title("📄 Resume Upload")
    st.write(f"Welcome, {st.session_state.get('user_email', 'User')}!")

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
                    st.session_state.get('user_id')
                )
                if result:
                    # Store success message in session state
                    st.session_state.upload_success = f"Successfully processed {uploaded_file.name}!"
                    st.success(st.session_state.upload_success)
                    # Set reset flag for the uploader
                    st.session_state.reset_single_upload = True
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
                st.session_state.bulk_upload_success = f"Successfully processed {success_count} out of {len(uploaded_files)} files"
                st.success(st.session_state.bulk_upload_success)
                
                # Show failed files if any
                failed_files = [name for name, success in results if not success]
                if failed_files:
                    st.warning(f"Failed to process: {', '.join(failed_files)}")
                
                # Set reset flag for the uploader
                st.session_state.reset_bulk_upload = True
                st.rerun()

    # Display any stored success messages
    if st.session_state.get('upload_success'):
        st.success(st.session_state.upload_success)
        # Clear the message after displaying
        del st.session_state.upload_success
    
    if st.session_state.get('bulk_upload_success'):
        st.success(st.session_state.bulk_upload_success)
        # Clear the message after displaying
        del st.session_state.bulk_upload_success

    # Add a logout button at the bottom
    st.markdown("---")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.switch_page("pages/login.py")

if __name__ == "__main__":
    main() 