import os
from supabase import create_client, Client
from typing import Dict, Optional, List
import uuid
from datetime import datetime, timezone
import json
import logging
from functools import lru_cache
import tempfile

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        logger.info("Initializing SupabaseClient")
        try:
            self.client: Client = create_client(
                supabase_url=os.getenv("SUPABASE_URL"),
                supabase_key=os.getenv("SUPABASE_KEY")
            )
            logger.info("Successfully initialized Supabase client")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}", exc_info=True)
            raise
        self._local_cache = {}

    @lru_cache(maxsize=1000)
    def store_resume_file(self, file_content: bytes, file_name: str) -> str:
        """Store resume file in Supabase storage with caching"""
        try:
            logger.info(f"Storing resume file: {file_name}")
            # Generate a unique filename
            file_base, file_ext = os.path.splitext(file_name)
            unique_filename = f"{file_base}_{uuid.uuid4().hex[:8]}{file_ext}"
            logger.debug(f"Generated unique filename: {unique_filename}")
            
            # Upload to Supabase storage
            logger.debug("Uploading file to Supabase storage")
            result = self.client.storage.from_('resumes').upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            
            # Get the public URL
            file_url = self.client.storage.from_('resumes').get_public_url(unique_filename)
            logger.info(f"Successfully stored resume file. URL: {file_url}")
            return file_url
                
        except Exception as e:
            logger.error(f"Error storing resume file: {str(e)}", exc_info=True)
            raise Exception(f"Error storing resume file: {str(e)}")

    def _format_array_for_postgres(self, arr: List) -> str:
        """
        Format a Python list as a PostgreSQL array string
        """
        if not arr:
            return '{}'
        # Escape single quotes and wrap each element in quotes
        formatted = [f'"{str(item).replace("\"", "\\\"")}"' for item in arr]
        return '{' + ','.join(formatted) + '}'

    def store_resume_data(self, data: Dict) -> Dict:
        """Store resume data in Supabase"""
        try:
            logger.info("Storing resume data in Supabase")
            parsed_data = data.get('parsed_data', {})
            
            # Extract data from parsed_data
            personal_info = parsed_data.get('personal_info', {})
            work_experience = parsed_data.get('work_experience', {})
            skills_and_tools = parsed_data.get('skills_and_tools', {})
            education_and_certifications = parsed_data.get('education_and_certifications', {})
            additional_info = parsed_data.get('additional_info', {})
            
            # Prepare data for storage
            resume_data = {
                'id': str(uuid.uuid4()),
                'file_name': os.path.basename(data.get('file_url', '')),
                'file_type': 'pdf',
                'file_path': data.get('file_url'),
                
                # Personal Information
                'full_name': personal_info.get('full_name'),
                'email': personal_info.get('email'),
                'phone': personal_info.get('phone'),
                'location': personal_info.get('location'),
                'linkedin_url': personal_info.get('linkedin_url'),
                
                # Work Experience
                'total_years_experience': work_experience.get('total_years_experience'),
                'current_or_last_job_title': work_experience.get('current_or_last_job_title'),
                'previous_job_titles': work_experience.get('previous_job_titles', []),
                'companies_worked_at': work_experience.get('companies_worked_at', []),
                'employment_type': work_experience.get('employment_type'),
                'availability': work_experience.get('availability'),
                
                # Skills and Tools
                'skills': skills_and_tools.get('skills', []),
                'skill_categories': skills_and_tools.get('skill_categories', {}),
                'tools_technologies': skills_and_tools.get('tools_technologies', []),
                
                # Education and Certifications
                'education': education_and_certifications.get('education', []),
                'degree_level': education_and_certifications.get('degree_level', []),
                'certifications': education_and_certifications.get('certifications', []),
                
                # Additional Information
                'summary_statement': additional_info.get('summary_statement'),
                'languages_spoken': additional_info.get('languages_spoken', []),
                
                # Raw and Processed Data
                'parsed_data': parsed_data,
                
                # Metadata
                'uploaded_by': 'system'
            }
            
            logger.debug(f"Prepared resume data for storage: {json.dumps(resume_data, indent=2)}")
            
            # Insert data into resumes table
            logger.debug("Inserting data into resumes table")
            try:
                result = self.client.table('resumes').insert(resume_data).execute()
                
                if not result.data:
                    logger.error("Failed to store resume data - no data returned from insert")
                    raise Exception("Failed to store resume data")
                
                logger.info(f"Successfully stored resume data with ID: {resume_data['id']}")
                return result.data[0]
            except Exception as insert_error:
                # Check if it's a materialized view permission error
                if isinstance(insert_error, Exception) and 'must be owner of materialized view dashboard_metrics' in str(insert_error):
                    logger.warning("Materialized view permission error - proceeding with insert anyway")
                    # Try to insert without the trigger
                    result = self.client.table('resumes').insert(resume_data).execute()
                    if not result.data:
                        raise Exception("Failed to store resume data")
                    return result.data[0]
                else:
                    raise
            
        except Exception as e:
            logger.error(f"Error storing resume data: {str(e)}", exc_info=True)
            raise

    @lru_cache(maxsize=1000)
    def get_resume_data(self, id: str) -> Optional[Dict]:
        """Retrieve resume data from Supabase database with caching"""
        try:
            logger.debug(f"Retrieving resume data for ID: {id}")
            result = self.client.table('resumes').select('*').eq('id', id).execute()
            if result.data:
                logger.debug(f"Successfully retrieved resume data for ID: {id}")
                return result.data[0]
            logger.warning(f"No resume data found for ID: {id}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving resume data: {str(e)}", exc_info=True)
            raise Exception(f"Error retrieving resume data: {str(e)}")

    def get_cached_resume_data(self, file_hash: str) -> Optional[Dict]:
        """Retrieve cached resume data using file hash with two-level caching"""
        try:
            logger.debug(f"Retrieving cached resume data for hash: {file_hash}")
            # Check local cache first
            if file_hash in self._local_cache:
                logger.debug("Found data in local cache")
                return self._local_cache[file_hash]

            # If not in local cache, check Supabase cache
            logger.debug("Checking Supabase cache")
            result = self.client.table('resume_cache').select('*').eq('file_hash', file_hash).execute()
            if result.data:
                # Store in local cache
                logger.debug("Found data in Supabase cache")
                self._local_cache[file_hash] = result.data[0]['data']
                return result.data[0]['data']
            logger.debug("No cached data found")
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached resume data: {str(e)}", exc_info=True)
            return None

    def cache_resume_data(self, file_hash: str, data: Dict) -> None:
        """Cache resume data using file hash with two-level caching"""
        try:
            logger.debug(f"Caching resume data for hash: {file_hash}")
            # Store in local cache
            self._local_cache[file_hash] = data

            # Store in Supabase cache
            cache_data = {
                'file_hash': file_hash,
                'data': data,
                'updated_at': datetime.utcnow().isoformat()
            }

            # Use upsert to handle both insert and update cases
            logger.debug("Storing data in Supabase cache")
            self.client.table('resume_cache').upsert(cache_data).execute()
            logger.debug("Successfully cached resume data")

        except Exception as e:
            logger.error(f"Error caching resume data: {str(e)}", exc_info=True)
            # If there's an error with Supabase cache, at least we have the local cache 

    def save_recruiter_notes(self, recruiter_id, candidate_id, outreach_message, screening_questions):
        """Save recruiter notes including outreach message and screening questions"""
        try:
            # Prepare the data
            data = {
                'recruiter_id': recruiter_id,
                'candidate_id': candidate_id,
                'outreach_message': outreach_message,
                'screening_questions': screening_questions,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            # Insert into recruiter_notes table
            response = self.client.table('recruiter_notes').insert(data).execute()
            
            if response.error:
                logger.error(f"Error saving recruiter notes: {response.error}")
                return False
            
            return True

        except Exception as e:
            logger.error(f"Error saving recruiter notes: {str(e)}")
            return False 