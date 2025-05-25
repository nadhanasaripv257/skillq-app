import os
from supabase import create_client, Client
from typing import Dict, Optional, List
import uuid
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )

    def store_resume_file(self, file_path: str, file_name: str) -> str:
        """Store resume file in Supabase storage"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Upload to Supabase storage
            result = self.client.storage.from_('resumes').upload(
                path=file_name,
                file=file_data,
                file_options={"content-type": "application/pdf"}
            )
            
            # Get the public URL
            file_url = self.client.storage.from_('resumes').get_public_url(file_name)
            return file_url
        except Exception as e:
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
            parsed_data = data.get('parsed_data', {})
            personal_info = parsed_data.get('personal_info', {})
            work_experience = parsed_data.get('work_experience', {})
            skills_and_tools = parsed_data.get('skills_and_tools', {})
            education_and_certifications = parsed_data.get('education_and_certifications', {})
            additional_info = parsed_data.get('additional_info', {})
            
            # Prepare data for storage
            resume_data = {
                'resume_id': str(uuid.uuid4()),
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
                'skills': skills_and_tools.get('skills', [])[:10],  # Limit to 10 skills
                'skill_categories': skills_and_tools.get('skill_categories', {}),
                'tools_technologies': skills_and_tools.get('tools_technologies', []),
                
                # Education and Certifications
                'education': education_and_certifications.get('education', []),
                'degree_level': education_and_certifications.get('degree_level', []),
                'certifications': education_and_certifications.get('certifications', []),
                
                # Additional Information
                'summary_statement': additional_info.get('summary_statement'),
                'languages_spoken': additional_info.get('languages_spoken', [])
            }
            
            # Insert data into resumes table
            result = self.client.table('resumes').insert(resume_data).execute()
            
            if not result.data:
                raise Exception("Failed to store resume data")
            
            return result.data[0]
            
        except Exception as e:
            logger.error(f"Error storing resume data: {str(e)}")
            raise

    def get_resume_data(self, id: str) -> Optional[Dict]:
        """Retrieve resume data from Supabase database"""
        try:
            result = self.client.table('resumes').select('*').eq('id', id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Error retrieving resume data: {str(e)}")

    def get_cached_resume_data(self, file_hash: str) -> Optional[Dict]:
        """Retrieve cached resume data using file hash"""
        try:
            result = self.client.table('resume_cache').select('*').eq('file_hash', file_hash).execute()
            if result.data:
                return result.data[0]['data']
            return None
        except Exception as e:
            # If the cache table doesn't exist or there's an error, return None
            return None

    def cache_resume_data(self, file_hash: str, data: Dict) -> None:
        """Cache resume data using file hash"""
        try:
            # First try to update existing cache
            result = self.client.table('resume_cache').update({
                'data': data,
                'updated_at': 'now()'
            }).eq('file_hash', file_hash).execute()
            
            # If no rows were updated, insert new cache entry
            if not result.data:
                self.client.table('resume_cache').insert({
                    'file_hash': file_hash,
                    'data': data
                }).execute()
        except Exception as e:
            # If the cache table doesn't exist, create it
            try:
                self.client.table('resume_cache').create({
                    'file_hash': 'text primary key',
                    'data': 'jsonb',
                    'created_at': 'timestamp with time zone default timezone(\'utc\'::text, now())',
                    'updated_at': 'timestamp with time zone default timezone(\'utc\'::text, now())'
                }).execute()
                
                # Try inserting again
                self.client.table('resume_cache').insert({
                    'file_hash': file_hash,
                    'data': data
                }).execute()
            except Exception as create_error:
                # If we can't create the table, just log the error and continue
                print(f"Error creating cache table: {str(create_error)}") 