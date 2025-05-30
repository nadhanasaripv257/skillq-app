import os
from typing import Dict, List, Optional, Tuple
from backend.supabase_client import SupabaseClient
from backend.openai_client import OpenAIClient
from PyPDF2 import PdfReader
from backend.resume_parser import ResumeParser
from functools import lru_cache
import hashlib
import concurrent.futures
from io import BytesIO
import tempfile
import logging
import json

logger = logging.getLogger(__name__)

class ResumeProcessor:
    def __init__(self):
        logger.info("Initializing ResumeProcessor")
        self.supabase = SupabaseClient()
        self.openai = OpenAIClient()
        self.parser = ResumeParser()
        self._cache = {}

    @lru_cache(maxsize=1000)
    def _get_file_hash(self, file_content: bytes) -> str:
        """Generate a hash of the file content for caching"""
        return hashlib.md5(file_content).hexdigest()

    @lru_cache(maxsize=1000)
    def read_pdf(self, file_content: bytes) -> str:
        """
        Read text content from a PDF file with caching
        """
        try:
            logger.debug("Reading PDF content")
            pdf_file = BytesIO(file_content)
            reader = PdfReader(pdf_file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            logger.debug(f"Successfully read PDF content, length: {len(text)}")
            return text
        except Exception as e:
            logger.error(f"Error reading PDF file: {str(e)}", exc_info=True)
            raise Exception(f"Error reading PDF file: {str(e)}")

    def calculate_risk_score(self, parsed_data: Dict) -> Tuple[int, List[str]]:
        """
        Calculate risk score and identify issues in the resume based on the parsed data.
        Risk score is on a scale of 0-10, where:
        0-2: Low risk
        3-5: Medium risk
        6-8: High risk
        9-10: Very high risk
        
        Risk Factors and Points:
        - Overlapping roles (2 points)
        - Unrealistic skill claims (1 point)
        - Multiple short job stints (2 points)
        - Inconsistent title progression (1 point)
        - Not enough details in resume (1 point)
        - Missing key information (1 point)
        - Education-job mismatch (1 point)
        - Rapid career progression (1 point)
        
        Returns:
            Tuple[int, List[str]]: (risk_score, list_of_issues)
        """
        risk_score = 0
        issues = []
        
        try:
            work_experience = parsed_data.get('work_experience', {})
            skills_and_tools = parsed_data.get('skills_and_tools', {})
            personal_info = parsed_data.get('personal_info', {})
            education = parsed_data.get('education_and_certifications', {})
            
            # Check for missing key information (1 point)
            missing_info = []
            if not personal_info.get('email'):
                missing_info.append("email")
            if not personal_info.get('phone'):
                missing_info.append("phone")
            if not personal_info.get('location'):
                missing_info.append("location")
            if not education.get('education'):
                missing_info.append("education details")
            
            if missing_info:
                risk_score += 1
                issues.append(f"Missing key information: {', '.join(missing_info)}")
            
            # Check for overlapping roles (2 points)
            job_titles = work_experience.get('previous_job_titles', [])
            if len(set(job_titles)) < len(job_titles):
                risk_score += 2
                issues.append("Overlapping roles detected in work history")
            
            # Check for unrealistic skill claims (1 point)
            skills = skills_and_tools.get('skills', [])
            years_experience = work_experience.get('total_years_experience', 0)
            
            if years_experience > 0:
                skill_density = len(skills) / years_experience
                if skill_density > 3:  # More than 3 skills per year of experience
                    risk_score += 1
                    issues.append(f"High skill density ({skill_density:.1f} skills/year) for experience level")
            
            # Check for multiple short job stints (2 points)
            companies = work_experience.get('companies_worked_at', [])
            if len(companies) > 3 and years_experience < 5:
                risk_score += 2
                issues.append("Multiple short job stints detected")
            
            # Check for inconsistent title progression (1 point)
            if len(job_titles) > 1:
                if any('senior' in title.lower() for title in job_titles[:-1]) and 'senior' not in job_titles[-1].lower():
                    risk_score += 1
                    issues.append("Inconsistent title progression detected")
            
            # Check for insufficient details (1 point)
            if not work_experience.get('summary_statement') or len(work_experience.get('summary_statement', '')) < 100:
                risk_score += 1
                issues.append("Insufficient details in resume")
            
            # Check for education-job mismatch (1 point)
            degree_level = education.get('degree_level', [])
            if degree_level and work_experience.get('current_or_last_job_title'):
                current_title = work_experience['current_or_last_job_title'].lower()
                if any('phd' in level.lower() or 'doctorate' in level.lower() for level in degree_level) and \
                   any(word in current_title for word in ['junior', 'entry', 'associate', 'trainee']):
                    risk_score += 1
                    issues.append("Education level appears mismatched with current role")
            
            # Check for rapid career progression (1 point)
            if len(job_titles) > 2 and years_experience < 3:
                risk_score += 1
                issues.append("Rapid career progression detected")
            
            # Add risk level to issues
            risk_level = "Low"
            if risk_score >= 9:
                risk_level = "Very High"
            elif risk_score >= 6:
                risk_level = "High"
            elif risk_score >= 3:
                risk_level = "Medium"
            
            issues.insert(0, f"Risk Level: {risk_level} ({risk_score}/10)")
            
            return risk_score, issues
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {str(e)}", exc_info=True)
            return 0, ["Error calculating risk score"]

    def process_resume(self, file_path: str) -> Dict:
        """
        Process a resume file and return structured data
        """
        try:
            logger.info(f"Processing resume file: {file_path}")
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            return self.process_resume_content(file_content, os.path.basename(file_path))

        except Exception as e:
            logger.error(f"Error in resume processing workflow: {str(e)}", exc_info=True)
            raise Exception(f"Error in resume processing workflow: {str(e)}")

    def process_resume_content(self, file_content: bytes, file_name: str) -> Dict:
        """Process resume content and return structured data"""
        try:
            logger.info(f"Processing resume content for file: {file_name}")
            
            # Parse resume using ResumeParser
            pii_data, sanitized_content = self.parser.process_resume(file_content, file_name)
            logger.debug(f"Extracted PII data: {json.dumps(pii_data, indent=2)}")
            
            # Parse resume using OpenAI
            structured_data = self.openai.parse_resume(sanitized_content)
            logger.debug(f"Extracted structured data: {json.dumps(structured_data, indent=2)}")
            
            # Extract location components
            location = structured_data.get('personal_info', {}).get('location', '')
            location_parts = [part.strip() for part in location.split(',')] if location else []
            
            # Extract city, state, and country
            city = location_parts[0] if len(location_parts) > 0 else None
            state = location_parts[1] if len(location_parts) > 1 else None
            country = location_parts[2] if len(location_parts) > 2 else 'Australia'  # Default to Australia if not specified
            
            # Merge the data with proper structure
            parsed_data = {
                'personal_info': {
                    'full_name': pii_data.get('full_name'),
                    'email': pii_data.get('email'),
                    'phone': pii_data.get('phone'),
                    'location': city,  # Store only city in location field
                    'state': state,    # Store state separately
                    'country': country, # Store country separately
                    'linkedin_url': structured_data.get('personal_info', {}).get('linkedin_url')
                },
                'work_experience': {
                    'total_years_experience': structured_data.get('work_experience', {}).get('total_years_experience', 0),
                    'current_or_last_job_title': structured_data.get('work_experience', {}).get('current_or_last_job_title'),
                    'previous_job_titles': structured_data.get('work_experience', {}).get('previous_job_titles', []),
                    'companies_worked_at': structured_data.get('work_experience', {}).get('companies_worked_at', []),
                    'employment_type': structured_data.get('work_experience', {}).get('employment_type'),
                    'availability': structured_data.get('work_experience', {}).get('availability')
                },
                'skills_and_tools': {
                    'skills': structured_data.get('skills_and_tools', {}).get('skills', []),
                    'skill_categories': structured_data.get('skills_and_tools', {}).get('skill_categories', {}),
                    'tools_technologies': structured_data.get('skills_and_tools', {}).get('tools_technologies', [])
                },
                'education_and_certifications': {
                    'education': structured_data.get('education_and_certifications', {}).get('education', []),
                    'degree_level': structured_data.get('education_and_certifications', {}).get('degree_level', []),
                    'certifications': structured_data.get('education_and_certifications', {}).get('certifications', [])
                },
                'additional_info': {
                    'summary_statement': structured_data.get('additional_info', {}).get('summary_statement'),
                    'languages_spoken': structured_data.get('additional_info', {}).get('languages_spoken', [])
                }
            }
            
            # Calculate risk score
            risk_score, issues = self.calculate_risk_score(parsed_data)
            logger.debug(f"Calculated risk score: {risk_score}")
            logger.debug(f"Identified issues: {json.dumps(issues, indent=2)}")
            
            # Generate search_blob using LLM
            search_blob_prompt = f"Given the candidate's resume data — including job titles, work experience, skills, tools, technologies, and education — generate a flat list of only relevant and related keywords. Include direct skills, tools, technologies, known synonyms, and similar job titles (e.g., for 'Customer Support', include 'Help Desk', 'Client Coordinator', 'Customer Coordinator'). Return only the keywords in lowercase, separated by a pipe (|). No extra text. No duplicates. Example: customer support|help desk|client coordinator|zendesk|crm|ticketing system|communication skills.\n\nCandidate Details:\n" + \
                                f"Current Role: {parsed_data['work_experience']['current_or_last_job_title']}\n" + \
                                f"Previous Roles: {', '.join(parsed_data['work_experience']['previous_job_titles'])}\n" + \
                                f"Skills: {', '.join(parsed_data['skills_and_tools']['skills'])}\n" + \
                                f"Tools: {', '.join(parsed_data['skills_and_tools']['tools_technologies'])}\n" + \
                                f"Experience: {parsed_data['work_experience']['total_years_experience']} years"
            search_blob = self.openai.generate_text(search_blob_prompt)
            logger.debug(f"Generated search_blob: {search_blob}")
            
            # Store data in Supabase
            data = {
                'file_url': f"https://{self.supabase.project_ref}.supabase.co/storage/v1/object/public/resumes/{file_name}",
                'parsed_data': parsed_data,
                'risk_score': risk_score,
                'issues': issues,
                'search_blob': search_blob
            }
            
            logger.debug(f"Prepared data for storage: {json.dumps(data, indent=2)}")
            result = self.supabase.store_resume_data(data)
            logger.info(f"Successfully stored resume data with ID: {result.get('id')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing resume content: {str(e)}", exc_info=True)
            raise

    def get_resume_data(self, id: str) -> Optional[Dict]:
        """
        Retrieve resume data from Supabase
        """
        try:
            logger.debug(f"Retrieving resume data for ID: {id}")
            return self.supabase.get_resume_data(id)
        except Exception as e:
            logger.error(f"Error retrieving resume data: {str(e)}", exc_info=True)
            raise Exception(f"Error retrieving resume data: {str(e)}") 