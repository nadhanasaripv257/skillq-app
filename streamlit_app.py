import streamlit as st
import os
import sys
from pathlib import Path
import tempfile

# Add the backend directory to Python path
sys.path.append(str(Path(__file__).parent))

from backend.resume_processor import ResumeProcessor

def save_uploaded_file(uploaded_file):
    """Save the uploaded file to a temporary location and return the path"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"Error saving file: {str(e)}")
        return None

def display_resume_data(data):
    """Display the processed resume data in a structured format"""
    st.subheader("Resume Analysis Results")
    
    # Personal Information
    with st.expander("Personal Information", expanded=True):
        st.write(f"**Name:** {data.get('full_name', 'Not provided')}")
        st.write(f"**Email:** {data.get('email', 'Not provided')}")
        st.write(f"**Phone:** {data.get('phone', 'Not provided')}")
        st.write(f"**Location:** {data.get('location', 'Not provided')}")
        st.write(f"**LinkedIn:** {data.get('linkedin_url', 'Not provided')}")
    
    # Work Experience
    with st.expander("Work Experience", expanded=True):
        st.write(f"**Total Years Experience:** {data.get('total_years_experience', 'Not provided')}")
        st.write(f"**Current/Last Job Title:** {data.get('current_or_last_job_title', 'Not provided')}")
        st.write("**Previous Job Titles:**")
        for title in data.get('previous_job_titles', []):
            st.write(f"- {title}")
        st.write("**Companies Worked At:**")
        for company in data.get('companies_worked_at', []):
            st.write(f"- {company}")
        st.write(f"**Employment Type:** {data.get('employment_type', 'Not provided')}")
        st.write(f"**Availability:** {data.get('availability', 'Not provided')}")
    
    # Skills and Tools
    with st.expander("Skills and Tools", expanded=True):
        st.write("**Skills:**")
        for skill in data.get('skills', []):
            st.write(f"- {skill}")
        st.write("**Tools and Technologies:**")
        for tool in data.get('tools_technologies', []):
            st.write(f"- {tool}")
        st.write("**Skill Categories:**")
        for category, skills in data.get('skill_categories', {}).items():
            st.write(f"**{category}:**")
            for skill in skills:
                st.write(f"- {skill}")
    
    # Education and Certifications
    with st.expander("Education and Certifications", expanded=True):
        st.write("**Education:**")
        for edu in data.get('education', []):
            st.write(f"- {edu}")
        st.write("**Degree Levels:**")
        for degree in data.get('degree_level', []):
            st.write(f"- {degree}")
        st.write("**Certifications:**")
        for cert in data.get('certifications', []):
            st.write(f"- {cert}")
    
    # Additional Information
    with st.expander("Additional Information", expanded=True):
        st.write(f"**Summary Statement:** {data.get('summary_statement', 'Not provided')}")
        st.write("**Languages Spoken:**")
        for lang in data.get('languages_spoken', []):
            st.write(f"- {lang}")

def main():
    st.set_page_config(page_title="SkillQ", page_icon="🧠", layout="wide")
    
    st.title("SkillQ - Resume Analysis")
    st.markdown("Upload a resume to analyze and extract key information.")
    
    # File upload
    uploaded_file = st.file_uploader("Choose a resume file (PDF)", type=['pdf'])
    
    if uploaded_file is not None:
        # Save the uploaded file
        file_path = save_uploaded_file(uploaded_file)
        
        if file_path:
            try:
                # Process the resume
                processor = ResumeProcessor()
                result = processor.process_resume(file_path)
                
                # Display the results
                display_resume_data(result)
                
                # Clean up the temporary file
                os.unlink(file_path)
                
            except Exception as e:
                st.error(f"Error processing resume: {str(e)}")
                if file_path:
                    os.unlink(file_path)

if __name__ == "__main__":
    main()

#fixed error