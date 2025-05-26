import os
from supabase import create_client, Client
from typing import Dict, Optional, List
import uuid
from datetime import datetime
import json
import logging
from functools import lru_cache
import tempfile

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.client: Client = create_client(
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY")
        )
        self._local_cache = {}

    @lru_cache(maxsize=1000)
    def store_resume_file(self, file_content: bytes, file_name: str) -> str:
        """Store resume file in Supabase storage with caching"""
        try:
            # Generate a unique filename
            file_base, file_ext = os.path.splitext(file_name)
            unique_filename = f"{file_base}_{uuid.uuid4().hex[:8]}{file_ext}"
            
            # Upload to Supabase storage
            result = self.client.storage.from_('resumes').upload(
                path=unique_filename,
                file=file_content,
                file_options={"content-type": "application/pdf"}
            )
            
            # Get the public URL
            file_url = self.client.storage.from_('resumes').get_public_url(unique_filename)
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
            
            # Prepare data for storage
            resume_data = {
                'id': str(uuid.uuid4()),
                'file_name': os.path.basename(data.get('file_url', '')),
                'file_type': 'pdf',
                'file_path': data.get('file_url'),
                'parsed_data': parsed_data,
                'uploaded_by': 'system'
            }
            
            # Insert data into resumes table
            result = self.client.table('resumes').insert(resume_data).execute()
            
            if not result.data:
                raise Exception("Failed to store resume data")
            
            return result.data[0]
            
        except Exception as e:
            logger.error(f"Error storing resume data: {str(e)}")
            raise

    @lru_cache(maxsize=1000)
    def get_resume_data(self, id: str) -> Optional[Dict]:
        """Retrieve resume data from Supabase database with caching"""
        try:
            result = self.client.table('resumes').select('*').eq('id', id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            raise Exception(f"Error retrieving resume data: {str(e)}")

    def get_cached_resume_data(self, file_hash: str) -> Optional[Dict]:
        """Retrieve cached resume data using file hash with two-level caching"""
        try:
            # Check local cache first
            if file_hash in self._local_cache:
                return self._local_cache[file_hash]

            # If not in local cache, check Supabase cache
            result = self.client.table('resume_cache').select('*').eq('file_hash', file_hash).execute()
            if result.data:
                # Store in local cache
                self._local_cache[file_hash] = result.data[0]['data']
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error retrieving cached resume data: {str(e)}")
            return None

    def cache_resume_data(self, file_hash: str, data: Dict) -> None:
        """Cache resume data using file hash with two-level caching"""
        try:
            # Store in local cache
            self._local_cache[file_hash] = data

            # Store in Supabase cache
            cache_data = {
                'file_hash': file_hash,
                'data': data,
                'updated_at': datetime.utcnow().isoformat()
            }

            # Use upsert to handle both insert and update cases
            self.client.table('resume_cache').upsert(cache_data).execute()

        except Exception as e:
            logger.error(f"Error caching resume data: {str(e)}")
            # If there's an error with Supabase cache, at least we have the local cache 