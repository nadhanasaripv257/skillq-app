import os
import logging
from typing import Dict, Optional, Tuple
import docx2txt
from pdfminer.high_level import extract_text as pdf_extract_text
import tempfile
from openai import OpenAI
import json

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResumeParser:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        self.client = OpenAI(api_key=api_key)

    def clean_text(self, text: str) -> str:
        """Clean text by removing null bytes and invalid Unicode characters"""
        if not text:
            return ""
        
        # Remove null bytes and control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        return text

    def extract_text_from_file(self, file_path: str) -> str:
        """Extract text from PDF or DOCX file"""
        try:
            if file_path.lower().endswith('.pdf'):
                text = pdf_extract_text(file_path)
            elif file_path.lower().endswith('.docx'):
                text = docx2txt.process(file_path)
            else:
                raise ValueError(f"Unsupported file format: {file_path}")
            
            return self.clean_text(text)
        except Exception as e:
            logger.error(f"Error extracting text from file: {str(e)}")
            raise

    def extract_pii(self, file_path: str) -> Dict:
        """Extract PII information from resume using OpenAI"""
        logger.info(f"Starting PII extraction for {file_path}")
        
        try:
            # Initialize PII data
            pii_data = {
                'email': None,
                'phone': None,
                'full_name': None,
                'companies_worked_at': [],
                'job_titles': [],
                'total_years': 0,
                'skills': [],
                'education': [],
                'raw_text': None
            }
            
            # Extract raw text first
            raw_text = self.extract_text_from_file(file_path)
            pii_data['raw_text'] = raw_text
            
            # Use OpenAI to extract information
            try:
                prompt = """
                Extract the following information from the resume text. If any information is not present, set it to null:

                Personal Information:
                - full_name: The candidate's full name (if present)
                - email: The candidate's email address (if present)
                - phone: The candidate's phone number (if present)

                Work Experience:
                - companies_worked_at: List of companies the candidate has worked at
                - job_titles: List of job titles held
                - total_years: Total years of experience (as a number)

                Skills and Education:
                - skills: List of skills mentioned
                - education: List of educational qualifications

                Format the response as a JSON object with the following structure:
                {
                    "full_name": "string or null",
                    "email": "string or null",
                    "phone": "string or null",
                    "companies_worked_at": ["string"],
                    "job_titles": ["string"],
                    "total_years": number,
                    "skills": ["string"],
                    "education": ["string"]
                }

                Important:
                1. Always return the complete structure with all fields
                2. For arrays, return an empty array [] if no items found
                3. For numbers, return 0 if not found
                4. For strings, return null if not found
                """

                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are a resume parsing assistant. Extract structured information from resume text. Be precise and accurate in your extraction."},
                        {"role": "user", "content": f"{prompt}\n\nResume text:\n{raw_text}"}
                    ],
                    response_format={ "type": "json_object" }
                )

                # Parse the JSON response
                extracted_data = json.loads(response.choices[0].message.content)
                
                # Update PII data with extracted information
                pii_data['full_name'] = extracted_data.get('full_name')
                pii_data['email'] = extracted_data.get('email')
                pii_data['phone'] = extracted_data.get('phone')
                pii_data['companies_worked_at'] = extracted_data.get('companies_worked_at', [])
                pii_data['job_titles'] = extracted_data.get('job_titles', [])
                pii_data['total_years'] = extracted_data.get('total_years', 0)
                pii_data['skills'] = extracted_data.get('skills', [])
                pii_data['education'] = extracted_data.get('education', [])
                
            except Exception as e:
                logger.error(f"OpenAI extraction failed: {str(e)}")
                raise
            
            # Clean all extracted data
            for key, value in pii_data.items():
                if value:
                    if isinstance(value, str):
                        pii_data[key] = self.clean_text(str(value))
                    elif isinstance(value, list):
                        pii_data[key] = [self.clean_text(str(item)) for item in value]
            
            logger.info(f"PII extraction complete: {pii_data}")
            return pii_data
            
        except Exception as e:
            logger.error(f"Error in PII extraction: {str(e)}")
            return {
                'email': None,
                'phone': None,
                'full_name': None,
                'companies_worked_at': [],
                'job_titles': [],
                'total_years': 0,
                'skills': [],
                'education': [],
                'raw_text': None
            }

    def process_resume(self, file_content: bytes, file_name: str) -> Tuple[Dict, str]:
        """
        Process a resume file and return PII data and sanitized content
        
        Args:
            file_content: The raw bytes of the resume file
            file_name: The name of the file
            
        Returns:
            Tuple[Dict, str]: (PII data dictionary, sanitized content)
        """
        logger.info(f"Processing resume: {file_name}")
        
        try:
            # Create a temporary file to store the content
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Extract PII data using OpenAI
                pii_data = self.extract_pii(temp_file_path)
                
                # Get sanitized content
                sanitized_content = pii_data.get('raw_text', '')
                
                # Remove PII from content
                if pii_data['email']:
                    sanitized_content = sanitized_content.replace(pii_data['email'], '[EMAIL]')
                if pii_data['phone']:
                    sanitized_content = sanitized_content.replace(pii_data['phone'], '[PHONE]')
                if pii_data['full_name']:
                    sanitized_content = sanitized_content.replace(pii_data['full_name'], '[NAME]')

                logger.info("Resume processing complete")
                return pii_data, sanitized_content
                
            finally:
                # Clean up the temporary file
                os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"Error processing resume: {str(e)}")
            raise

def main():
    # Example usage
    parser = ResumeParser()
    
    # Test with a sample file
    try:
        pii_data, sanitized_content = parser.process_resume("path/to/resume.pdf")
        print("Extracted PII Data:")
        print(pii_data)
        print("\nSanitized Content:")
        print(sanitized_content[:500] + "...")  # Print first 500 chars
    except Exception as e:
        print(f"Error processing resume: {str(e)}")

if __name__ == "__main__":
    main() 