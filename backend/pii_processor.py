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

class PIIProcessor:
    def __init__(self):
        """Initialize the PII processor with Presidio"""
        try:
            # Ensure spaCy model is loaded
            try:
                spacy.load('en_core_web_lg')
            except OSError:
                logger.info("Downloading spaCy model...")
                spacy.cli.download('en_core_web_lg')
                spacy.load('en_core_web_lg')
            
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
                'address': None
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
                    pii_data['address'] = value
            
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
                'address': None
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
                'address': None
            } 