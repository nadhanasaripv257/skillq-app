import os
from typing import Dict, Tuple, List
import logging
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
import spacy
import re

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load spaCy model with runtime download if needed
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    from spacy.cli import download
    download("en_core_web_lg")
    nlp = spacy.load("en_core_web_lg")

class PIIProcessor:
    def __init__(self):
        """Initialize the PII processor with Presidio"""
        try:
            # Initialize NLP engine with spaCy
            nlp_engine = NlpEngineProvider().create_engine()
            
            # Initialize Presidio analyzer and anonymizer
            self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine)
            self.anonymizer = AnonymizerEngine()
            
            # Common false positives for name detection
            self.false_positives = {
                'docker', 'kubernetes', 'aws', 'azure', 'gcp', 'linux', 'windows',
                'macos', 'ios', 'android', 'python', 'java', 'javascript', 'typescript',
                'react', 'angular', 'vue', 'node', 'express', 'django', 'flask',
                'spring', 'hibernate', 'mysql', 'postgresql', 'mongodb', 'redis',
                'elasticsearch', 'kafka', 'rabbitmq', 'jenkins', 'gitlab', 'github',
                'bitbucket', 'jira', 'confluence', 'slack', 'teams', 'zoom', 'skype'
            }
            
            # Patterns for detailed address detection
            self.address_patterns = [
                r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Place|Pl)\b',
                r'\b(?:Apt|Apartment|Unit|Suite|Ste|Floor|Fl|#)\s*[A-Za-z0-9-]+\b',
                r'\b(?:PO Box|P.O. Box|P.O Box|Post Office Box)\s+[A-Za-z0-9-]+\b',
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'  # Email pattern
            ]
            
            logger.info("PII processor initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing PII processor: {str(e)}")
            raise

    def is_valid_name(self, name: str) -> bool:
        """
        Validate if a detected name is likely to be a real person's name
        
        Args:
            name: The detected name to validate
            
        Returns:
            bool: True if the name is likely valid, False otherwise
        """
        # Convert to lowercase for comparison
        name_lower = name.lower()
        
        # Check if it's in our false positives list
        if name_lower in self.false_positives:
            return False
            
        # Check if it's a single word (less likely to be a full name)
        if len(name.split()) < 2:
            return False
            
        # Check if it contains numbers or special characters
        if re.search(r'[0-9!@#$%^&*()_+\-=\[\]{};\'"\\|,.<>\/?]', name):
            return False
            
        # Check if it's too short or too long
        if len(name) < 4 or len(name) > 50:
            return False
            
        return True

    def is_detailed_address(self, text: str) -> bool:
        """
        Check if the text contains a detailed address that should be masked
        
        Args:
            text: The text to check
            
        Returns:
            bool: True if the text contains a detailed address, False otherwise
        """
        # Check for any of the address patterns
        for pattern in self.address_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def extract_location_components(self, text: str) -> Dict[str, str]:
        """
        Extract city, state, and country from location text
        
        Args:
            text: The location text to parse
            
        Returns:
            Dict containing city, state, and country
        """
        location = {
            'city': None,
            'state': None,
            'country': 'Australia'  # Default country
        }
        
        # Split by common separators
        parts = [part.strip() for part in re.split(r'[,;]', text)]
        
        if len(parts) >= 1:
            location['city'] = parts[0]
        if len(parts) >= 2:
            location['state'] = parts[1]
        if len(parts) >= 3:
            location['country'] = parts[2]
            
        return location

    def extract_pii(self, text: str) -> Dict:
        """
        Extract PII information from text using Presidio
        
        Args:
            text: The text to analyze
            
        Returns:
            Dict containing extracted PII information
        """
        try:
            # Define the entities we want to detect
            entities = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"]
            
            # Analyze the text
            results = self.analyzer.analyze(text=text, entities=entities, language="en")
            
            # Extract PII information
            pii_data = {
                'full_name': None,
                'email': None,
                'phone': None,
                'address': None,
                'location': {
                    'city': None,
                    'state': None,
                    'country': 'Australia'
                }
            }
            
            # Process results
            detected_names = []
            for result in results:
                entity_type = result.entity_type
                value = text[result.start:result.end]
                
                if entity_type == "PERSON":
                    if self.is_valid_name(value):
                        detected_names.append(value)
                elif entity_type == "EMAIL_ADDRESS":
                    pii_data['email'] = value
                elif entity_type == "PHONE_NUMBER":
                    pii_data['phone'] = value
                elif entity_type == "LOCATION":
                    if self.is_detailed_address(value):
                        pii_data['address'] = value
                    else:
                        # Extract location components for non-detailed addresses
                        location_components = self.extract_location_components(value)
                        pii_data['location'].update(location_components)
            
            # Use the most likely name (usually the first one in the document)
            if detected_names:
                pii_data['full_name'] = detected_names[0]
            
            logger.debug(f"Extracted PII data: {pii_data}")
            return pii_data
            
        except Exception as e:
            logger.error(f"Error extracting PII: {str(e)}")
            return {
                'full_name': None,
                'email': None,
                'phone': None,
                'address': None,
                'location': {
                    'city': None,
                    'state': None,
                    'country': 'Australia'
                }
            }

    def anonymize_text(self, text: str) -> Tuple[str, Dict]:
        """
        Anonymize text by replacing PII with specific tokens
        
        Args:
            text: The text to anonymize
            
        Returns:
            Tuple of (anonymized_text, pii_data)
        """
        try:
            # Extract PII first
            pii_data = self.extract_pii(text)
            
            # Create a copy of the text to anonymize
            anonymized_text = text
            
            # Replace PII with specific tokens
            if pii_data['full_name']:
                anonymized_text = anonymized_text.replace(pii_data['full_name'], "[NAME]")
            if pii_data['email']:
                anonymized_text = anonymized_text.replace(pii_data['email'], "[EMAIL]")
            if pii_data['phone']:
                anonymized_text = anonymized_text.replace(pii_data['phone'], "[PHONE]")
            if pii_data['address']:
                anonymized_text = anonymized_text.replace(pii_data['address'], "[ADDRESS]")
            
            logger.debug(f"Anonymized text length: {len(anonymized_text)}")
            return anonymized_text, pii_data
            
        except Exception as e:
            logger.error(f"Error anonymizing text: {str(e)}")
            return text, {
                'full_name': None,
                'email': None,
                'phone': None,
                'address': None,
                'location': {
                    'city': None,
                    'state': None,
                    'country': 'Australia'
                }
            } 