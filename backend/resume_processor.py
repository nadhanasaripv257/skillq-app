import os
from typing import Dict, List, Optional
from backend.supabase_client import SupabaseClient
from backend.openai_client import OpenAIClient
from PyPDF2 import PdfReader
from backend.resume_parser import ResumeParser
from functools import lru_cache
import hashlib
import concurrent.futures
from io import BytesIO
import tempfile

class ResumeProcessor:
    def __init__(self):
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
            pdf_file = BytesIO(file_content)
            reader = PdfReader(pdf_file)
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
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            return self.process_resume_content(file_content, os.path.basename(file_path))

        except Exception as e:
            raise Exception(f"Error in resume processing workflow: {str(e)}")

    def process_resume_content(self, file_content: bytes, file_name: str) -> Dict:
        """
        Process resume content directly and return structured data
        """
        try:
            # Generate file hash for caching
            file_hash = self._get_file_hash(file_content)
            
            # Check memory cache first
            if file_hash in self._cache:
                return self._cache[file_hash]
            
            # Check Supabase cache
            cached_data = self.supabase.get_cached_resume_data(file_hash)
            if cached_data:
                self._cache[file_hash] = cached_data
                return cached_data

            # Read the PDF file
            content = self.read_pdf(file_content)

            # Parse resume with OpenAI
            parsed_data = self.openai.parse_resume(content)

            # Store the resume file in Supabase
            file_url = self.supabase.store_resume_file(file_content, file_name)

            # Prepare the final data
            result_data = {
                'file_url': file_url,
                'parsed_data': parsed_data,
                'file_hash': file_hash
            }

            # Store the parsed data in Supabase
            id = self.supabase.store_resume_data(result_data)

            # Cache the results
            self._cache[file_hash] = result_data
            self.supabase.cache_resume_data(file_hash, result_data)

            return {
                'id': id,
                'parsed_data': parsed_data
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