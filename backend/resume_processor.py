import os
from typing import Dict, List, Optional
from backend.supabase_client import SupabaseClient
from backend.openai_client import OpenAIClient
import re
from PyPDF2 import PdfReader
from backend.resume_parser import ResumeParser
from functools import lru_cache
import hashlib

class ResumeProcessor:
    def __init__(self):
        self.supabase = SupabaseClient()
        self.openai = OpenAIClient()
        self.parser = ResumeParser()

    @lru_cache(maxsize=100)
    def _get_file_hash(self, file_path: str) -> str:
        """Generate a hash of the file content for caching"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def extract_pii(self, text: str) -> Dict[str, str]:
        """
        Extract PII from text using regex patterns
        """
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        # Phone pattern (handles various formats)
        phone_pattern = r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        # LinkedIn URL pattern
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w-]+/?'
        
        # Extract PII
        email = re.search(email_pattern, text)
        phone = re.search(phone_pattern, text)
        linkedin = re.search(linkedin_pattern, text)
        
        return {
            'email': email.group(0) if email else None,
            'phone': phone.group(0) if phone else None,
            'linkedin_url': linkedin.group(0) if linkedin else None
        }

    def anonymize_text(self, text: str, pii: Dict[str, str]) -> str:
        """
        Anonymize PII in text
        """
        anonymized = text
        for key, value in pii.items():
            if value:
                if isinstance(value, str):
                    anonymized = anonymized.replace(value, '[REDACTED]')
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            anonymized = anonymized.replace(item, '[REDACTED]')
        return anonymized

    @lru_cache(maxsize=100)
    def read_pdf(self, file_path: str) -> str:
        """
        Read text content from a PDF file with caching
        """
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"Error reading PDF file: {str(e)}")

    def process_resume(self, file_path: str) -> Dict:
        """
        Process a resume file and return structured data
        """
        try:
            # Generate file hash for caching
            file_hash = self._get_file_hash(file_path)
            
            # Check if we have cached results
            cached_data = self.supabase.get_cached_resume_data(file_hash)
            if cached_data:
                return cached_data

            # Read the PDF file
            content = self.read_pdf(file_path)

            # Extract PII using the ResumeParser
            pii_data = self.parser.extract_pii(file_path)
            
            # Anonymize content for OpenAI processing
            anonymized_content = self.anonymize_text(content, pii_data)

            # Parse resume with OpenAI
            parsed_data = self.openai.parse_resume(anonymized_content)
            
            # Update personal info with extracted PII
            if parsed_data.get('personal_info'):
                parsed_data['personal_info'].update({
                    'email': pii_data.get('email'),
                    'phone': pii_data.get('phone'),
                    'full_name': pii_data.get('full_name')
                })

            # Store the resume file in Supabase
            file_name = os.path.basename(file_path)
            file_url = self.supabase.store_resume_file(file_path, file_name)

            # Prepare the final data
            result_data = {
                'file_url': file_url,
                'parsed_data': parsed_data,
                'pii': pii_data,
                'file_hash': file_hash
            }

            # Store the parsed data in Supabase
            id = self.supabase.store_resume_data(result_data)

            # Cache the results
            self.supabase.cache_resume_data(file_hash, result_data)

            return {
                'id': id,
                'parsed_data': parsed_data,
                'pii': pii_data
            }

        except Exception as e:
            raise Exception(f"Error in resume processing workflow: {str(e)}")

    def get_resume_data(self, id: str) -> Optional[Dict]:
        """
        Retrieve resume data from Supabase
        """
        try:
            return self.supabase.get_resume_data(id)
        except Exception as e:
            raise Exception(f"Error retrieving resume data: {str(e)}") 