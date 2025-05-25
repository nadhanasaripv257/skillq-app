import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from backend.resume_processor import ResumeProcessor

def test_resume_processing():
    try:
        # Initialize the processor
        processor = ResumeProcessor()

        # Process the test resume
        result = processor.process_resume('backend/test_resume.pdf')

        # Print the results
        print("\nResume Processing Results:")
        print("-------------------------")
        print(f"Resume ID: {result['id']}")
        
        # Print Personal Information
        print("\nPersonal Information:")
        print("--------------------")
        for key, value in result['parsed_data']['personal_info'].items():
            print(f"{key}: {value}")

        # Print Work Experience
        print("\nWork Experience:")
        print("---------------")
        for key, value in result['parsed_data']['work_experience'].items():
            print(f"{key}: {value}")

        # Print Skills and Tools
        print("\nSkills and Tools:")
        print("----------------")
        print("Skills:", result['parsed_data']['skills_and_tools']['skills'])
        print("\nSkill Categories:")
        for category, skills in result['parsed_data']['skills_and_tools']['skill_categories'].items():
            print(f"{category}: {skills}")
        print("\nTools and Technologies:", result['parsed_data']['skills_and_tools']['tools_technologies'])

        # Print Education and Certifications
        print("\nEducation and Certifications:")
        print("---------------------------")
        print("Education:", result['parsed_data']['education_and_certifications']['education'])
        print("Degree Levels:", result['parsed_data']['education_and_certifications']['degree_level'])
        print("Certifications:", result['parsed_data']['education_and_certifications']['certifications'])

        # Print Additional Information
        print("\nAdditional Information:")
        print("---------------------")
        for key, value in result['parsed_data']['additional_info'].items():
            print(f"{key}: {value}")

        # Print PII (for verification)
        print("\nPII Information (for verification):")
        print("--------------------------------")
        for key, value in result['pii'].items():
            print(f"{key}: {value}")

        print("\nTest completed successfully!")

    except Exception as e:
        print(f"\nError during testing: {str(e)}")

if __name__ == "__main__":
    test_resume_processing() 