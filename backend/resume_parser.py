import os
import logging
from typing import Dict, Optional, Tuple
from pyresparser import ResumeParser as PyResParser
import docx2txt
from pdfminer.high_level import extract_text as pdf_extract_text
import re
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResumeParser:
    def __init__(self):
        pass

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
        """Extract PII information from resume using LLM and regex patterns"""
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
            
            # Use regex patterns to extract PII
            # Email pattern
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            email_match = re.search(email_pattern, raw_text)
            if email_match:
                pii_data['email'] = email_match.group(0)
            
            # Enhanced phone patterns with better validation
            phone_patterns = [
                # Look for labeled phone numbers first
                r'(?:phone|mobile|cell|tel|telephone)[\s:]+([+\d\s\-\(\)\.]{10,})',
                r'(?:ph|mob|tel)[\s:]+([+\d\s\-\(\)\.]{10,})',
                
                # Standard formats
                r'(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # Standard US format
                r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # Simple format
                r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',  # (123) 456-7890
                r'\+\d{1,3}\s*\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # International format
                
                # Additional formats
                r'\d{3}\.\d{3}\.\d{4}',  # 123.456.7890
                r'\d{3}\s\d{3}\s\d{4}',  # 123 456 7890
                r'\+\d{1,3}\.\d{3}\.\d{3}\.\d{4}',  # +1.123.456.7890
                r'\+\d{1,3}\s\d{3}\s\d{3}\s\d{4}'  # +1 123 456 7890
            ]
            
            # First try to find labeled phone numbers
            for pattern in phone_patterns[:2]:
                phone_match = re.search(pattern, raw_text, re.IGNORECASE)
                if phone_match:
                    phone = phone_match.group(1) if len(phone_match.groups()) > 0 else phone_match.group(0)
                    # Clean the phone number
                    phone = re.sub(r'[^\d+]', '', phone)
                    if len(phone) >= 10:  # Basic validation
                        pii_data['phone'] = phone
                        break
            
            # If no labeled phone found, try other patterns
            if not pii_data['phone']:
                for pattern in phone_patterns[2:]:
                    phone_match = re.search(pattern, raw_text)
                    if phone_match:
                        phone = phone_match.group(0)
                        # Clean the phone number
                        phone = re.sub(r'[^\d+]', '', phone)
                        if len(phone) >= 10:  # Basic validation
                            pii_data['phone'] = phone
                            break
            
            # Name pattern (look for common name indicators)
            name_indicators = [
                r'Name:\s*([A-Za-z\s]+)',
                r'Full Name:\s*([A-Za-z\s]+)',
                r'^([A-Za-z\s]+)$',  # Standalone name at start of line
                r'([A-Za-z\s]+)\s*\|'  # Name followed by separator
            ]
            
            for pattern in name_indicators:
                name_match = re.search(pattern, raw_text)
                if name_match:
                    pii_data['full_name'] = name_match.group(1).strip()
                    break
            
            # Use LLM to extract additional information
            try:
                parser = PyResParser(file_path)
                pyres_data = parser.get_extracted_data()
                
                # Only update PII if not already found by regex
                if not pii_data['email']:
                    pii_data['email'] = pyres_data.get('email')
                if not pii_data['phone']:
                    pii_data['phone'] = pyres_data.get('mobile_number')
                if not pii_data['full_name']:
                    pii_data['full_name'] = pyres_data.get('name')
                
                # Extract work experience
                if pyres_data.get('experience'):
                    for exp in pyres_data['experience']:
                        if exp.get('company'):
                            pii_data['companies_worked_at'].append(exp['company'])
                        if exp.get('title'):
                            pii_data['job_titles'].append(exp['title'])
                
                # Extract skills
                if pyres_data.get('skills'):
                    pii_data['skills'] = pyres_data['skills']
                
                # Extract education
                if pyres_data.get('degree'):
                    pii_data['education'] = [pyres_data['degree']]
                
                # Estimate total years
                if pyres_data.get('total_experience'):
                    try:
                        pii_data['total_years'] = int(pyres_data['total_experience'])
                    except (ValueError, TypeError):
                        pass
                
            except Exception as e:
                logger.error(f"LLM extraction failed: {str(e)}")
                # Continue with regex-extracted data
            
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
                # Extract PII data using LLM
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