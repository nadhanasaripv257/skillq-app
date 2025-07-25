import os
from supabase import create_client, Client
from postgrest import PostgrestClient
from typing import Dict, Optional, List
import uuid
from datetime import datetime, timezone
import json
import logging
from functools import lru_cache
import tempfile
import hashlib
from datetime import timedelta

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        logger.info("Initializing SupabaseClient")
        self._client = None
        self._project_ref = None
        self._local_cache = {}

    @property
    def client(self) -> Client:
        """Lazy load the Supabase client"""
        if self._client is None:
            try:
                # Create client with the service role key
                self._client = create_client(
                    supabase_url=os.getenv("SUPABASE_URL"),
                    supabase_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                )
                
                # Set the headers explicitly
                self._client.postgrest.headers = {
                    "apikey": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
                    "Authorization": f"Bearer {os.getenv('SUPABASE_SERVICE_ROLE_KEY')}"
                }
                
                # Extract project reference from Supabase URL
                self._project_ref = os.getenv("SUPABASE_URL").split("//")[1].split(".")[0]
                logger.info("Successfully initialized Supabase client")
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {str(e)}", exc_info=True)
                raise
        return self._client

    @property
    def project_ref(self) -> str:
        """Lazy load the project reference"""
        if self._project_ref is None:
            self._project_ref = os.getenv("SUPABASE_URL").split("//")[1].split(".")[0]
        return self._project_ref

    def get_authed_client(self, access_token: str) -> Client:
        """Create an authenticated client with the given access token"""
        try:
            client = create_client(
                supabase_url=os.getenv("SUPABASE_URL"),
                supabase_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            )
            # Set the auth header
            client.auth.set_session(access_token, "")
            # Override the postgrest client to include the auth token
            client.postgrest = PostgrestClient(
                f"{os.getenv('SUPABASE_URL')}/rest/v1",
                headers={
                    "apikey": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
                    "Authorization": f"Bearer {access_token}"
                }
            )
            return client
        except Exception as e:
            logger.error(f"Error creating authenticated client: {str(e)}")
            raise

    def table(self, table_name: str):
        """Expose the table method from the underlying Supabase client"""
        return self.client.table(table_name)

    @property
    def auth(self):
        """Expose the auth object from the underlying Supabase client"""
        return self.client.auth

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
        formatted = []
        for item in arr:
            # Replace double quotes with escaped double quotes
            escaped_item = str(item).replace('"', '\\"')
            formatted.append(f'"{escaped_item}"')
        return '{' + ','.join(formatted) + '}'

    def store_resume_data(self, data: Dict) -> Dict:
        """Store resume data in Supabase"""
        try:
            logger.info("Storing resume data in Supabase")
            logger.debug(f"Input data: {json.dumps(data, indent=2)}")
            
            parsed_data = data.get('parsed_data', {})
            logger.debug(f"Parsed data: {json.dumps(parsed_data, indent=2)}")
            
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
                
                # Personal Information - store only non-PII data
                'location': personal_info.get('location'),  # City only
                'state': personal_info.get('state'),        # State
                'country': personal_info.get('country'),    # Country
                'linkedin_url': personal_info.get('linkedin_url'),
                
                # Work Experience - ensure numeric fields have default values
                'total_years_experience': work_experience.get('total_years_experience', 0) or 0,
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
                
                # Risk Assessment - ensure numeric fields have default values
                'risk_score': data.get('risk_score', 0) or 0,
                'issues': data.get('issues', []),
                
                # Raw and Processed Data
                'parsed_data': parsed_data,
                
                # Metadata
                'uploaded_by': 'system',
                'uploaded_at': datetime.now(timezone.utc).isoformat(),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                
                # Search blob
                'search_blob': data.get('search_blob', '')
            }
            
            logger.debug(f"Prepared resume data for storage: {json.dumps(resume_data, indent=2)}")
            
            # Insert data into resumes table
            logger.debug("Inserting data into resumes table")
            result = self.client.table('resumes').insert(resume_data).execute()
            
            if not result.data:
                logger.error("Failed to store resume data - no data returned from insert")
                raise Exception("Failed to store resume data")
            
            logger.info(f"Successfully stored resume data with ID: {resume_data['id']}")
            logger.debug(f"Stored data: {json.dumps(result.data[0], indent=2)}")
            return result.data[0]
            
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

    def cache_outreach_message(self, candidate_id: str, query: str, outreach_data: Dict) -> bool:
        """Cache outreach message and screening questions in Supabase"""
        try:
            # Prepare cache data
            cache_data = {
                'candidate_id': candidate_id,
                'query_hash': hashlib.md5(query.encode()).hexdigest(),
                'outreach_data': outreach_data,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()  # 7-day TTL
            }

            # Use upsert to handle both insert and update cases
            response = self.client.table('outreach_cache').upsert(cache_data).execute()
            
            if response.error:
                logger.error(f"Error caching outreach message: {response.error}")
                return False
            
            return True

        except Exception as e:
            logger.error(f"Error caching outreach message: {str(e)}")
            return False

    def get_cached_outreach(self, candidate_id: str, query: str) -> Optional[Dict]:
        """Retrieve cached outreach message from Supabase"""
        try:
            query_hash = hashlib.md5(query.encode()).hexdigest()
            
            # Get cached data
            response = self.client.table('outreach_cache')\
                .select('*')\
                .eq('candidate_id', candidate_id)\
                .eq('query_hash', query_hash)\
                .lt('expires_at', datetime.now(timezone.utc).isoformat())\
                .execute()
            
            if response.data:
                return response.data[0]['outreach_data']
            return None

        except Exception as e:
            logger.error(f"Error retrieving cached outreach: {str(e)}")
            return None

    def store_pii_data(self, resume_id: str, pii_data: Dict) -> Dict:
        """Store PII data in the resumes_pii table"""
        try:
            logger.info(f"Storing PII data for resume {resume_id}")
            logger.debug(f"PII data: {json.dumps(pii_data, indent=2)}")
            
            # Prepare data for storage
            pii_record = {
                'resume_id': resume_id,
                'full_name': pii_data.get('full_name'),
                'email': pii_data.get('email'),
                'phone': pii_data.get('phone'),
                'address': pii_data.get('address'),
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Insert data into resumes_pii table
            result = self.client.table('resumes_pii').insert(pii_record).execute()
            
            logger.info(f"Successfully stored PII data for resume {resume_id}")
            return result.data[0] if result.data else None
            
        except Exception as e:
            logger.error(f"Error storing PII data: {str(e)}")
            raise 