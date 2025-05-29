import os
from openai import OpenAI
from typing import Dict, List
import json
import time

class OpenAIClient:
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables")
        self.client = OpenAI(api_key=api_key)

    def parse_resume(self, resume_text: str) -> Dict:
        """
        Parse resume text using OpenAI API to extract key information
        """
        try:
            prompt = """
            Extract the following information from the resume text. If any information is not present, set it to null:

            Personal Information:
            - full_name: The candidate's full name (if present)
            - email: The candidate's email address (if present)
            - phone: The candidate's phone number (if present)
            - location: The city and state or region (e.g., Melbourne, VIC)
            - linkedin_url: LinkedIn profile link if available

            Work Experience:
            - total_years_experience: A rough estimate of how many years of work experience the candidate has
            - current_or_last_job_title: Most recent or current job title
            - previous_job_titles: List of previous job titles held
            - companies_worked_at: List of companies the candidate has worked at
            - employment_type: Full-time / Contract / Freelance / Internship (if mentioned)
            - availability: "Available now" / "Notice period" / "Unavailable" (if mentioned)

            Skills and Tools:
            - skills: List of relevant skills (limit to 10 if very long)
            - skill_categories: Categorized version of the skills (e.g., Soft Skills, Tech Tools, Coordination)
            - tools_technologies: List of specific software or tools mentioned (e.g., Salesforce, Excel)

            Education and Certifications:
            - education: Full degree names and institutions
            - degree_level: Bachelors / Masters / Diploma / Certificate
            - certifications: Any relevant certifications (e.g., ITIL, PMP)

            Additional Information:
            - summary_statement: A brief professional summary from the resume (if available)
            - languages_spoken: List of any languages mentioned

            Format the response as a JSON object with the following structure:
            {
                "personal_info": {
                    "full_name": "string or null",
                    "email": "string or null",
                    "phone": "string or null",
                    "location": "string or null",
                    "linkedin_url": "string or null"
                },
                "work_experience": {
                    "total_years_experience": "number or null",
                    "current_or_last_job_title": "string or null",
                    "previous_job_titles": ["string"],
                    "companies_worked_at": ["string"],
                    "employment_type": "string or null",
                    "availability": "string or null"
                },
                "skills_and_tools": {
                    "skills": ["string"],
                    "skill_categories": {
                        "category_name": ["skill1", "skill2"]
                    },
                    "tools_technologies": ["string"]
                },
                "education_and_certifications": {
                    "education": ["string"],
                    "degree_level": ["string"],
                    "certifications": ["string"]
                },
                "additional_info": {
                    "summary_statement": "string or null",
                    "languages_spoken": ["string"]
                }
            }

            Important:
            1. Always return the complete structure with all fields, even if they are null or empty arrays
            2. For arrays, return an empty array [] if no items found, not null
            3. For objects, return an empty object {} if no data found, not null
            4. For numbers, return 0 if not found, not null
            5. For strings, return null if not found
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a resume parsing assistant. Extract structured information from resume text. Be precise and accurate in your extraction. Always return the complete data structure with all fields."},
                    {"role": "user", "content": f"{prompt}\n\nResume text:\n{resume_text}"}
                ],
                response_format={ "type": "json_object" }
            )

            # Parse the JSON response
            parsed_data = json.loads(response.choices[0].message.content)
            
            # Ensure all required fields are present with proper defaults
            default_structure = {
                "personal_info": {
                    "full_name": None,
                    "email": None,
                    "phone": None,
                    "location": None,
                    "linkedin_url": None
                },
                "work_experience": {
                    "total_years_experience": 0,
                    "current_or_last_job_title": None,
                    "previous_job_titles": [],
                    "companies_worked_at": [],
                    "employment_type": None,
                    "availability": None
                },
                "skills_and_tools": {
                    "skills": [],
                    "skill_categories": {},
                    "tools_technologies": []
                },
                "education_and_certifications": {
                    "education": [],
                    "degree_level": [],
                    "certifications": []
                },
                "additional_info": {
                    "summary_statement": None,
                    "languages_spoken": []
                }
            }
            
            # Merge the parsed data with defaults
            for section in default_structure:
                if section not in parsed_data:
                    parsed_data[section] = default_structure[section]
                else:
                    for field, default_value in default_structure[section].items():
                        if field not in parsed_data[section]:
                            parsed_data[section][field] = default_value
                        elif parsed_data[section][field] is None:
                            parsed_data[section][field] = default_value
            
            return parsed_data

        except Exception as e:
            logger.error(f"Error parsing resume with OpenAI: {str(e)}")
            # Return default structure on error
            return {
                "personal_info": {
                    "full_name": None,
                    "email": None,
                    "phone": None,
                    "location": None,
                    "linkedin_url": None
                },
                "work_experience": {
                    "total_years_experience": 0,
                    "current_or_last_job_title": None,
                    "previous_job_titles": [],
                    "companies_worked_at": [],
                    "employment_type": None,
                    "availability": None
                },
                "skills_and_tools": {
                    "skills": [],
                    "skill_categories": {},
                    "tools_technologies": []
                },
                "education_and_certifications": {
                    "education": [],
                    "degree_level": [],
                    "certifications": []
                },
                "additional_info": {
                    "summary_statement": None,
                    "languages_spoken": []
                }
            }

    def extract_query_filters(self, query: str) -> Dict:
        """
        Extract search filters from a natural language query using OpenAI API
        """
        try:
            prompt = """
            Extract search filters from the given query. Return a JSON object with the following structure:
            {
                "role": "string or null",  // The main role/title being searched for
                "related_roles": ["string"],  // Related roles that could also match
                "related_keywords": ["string"],  // Keywords related to the role
                "location": "string or null",  // Location if specified
                "required_skills": ["string"],  // Required skills mentioned
                "experience_years_min": number or null  // Minimum years of experience if specified
            }

            Examples:
            Query: "Find me Python developers in Sydney with 3 years of experience"
            Response: {
                "role": "Python Developer",
                "related_roles": ["Software Developer", "Backend Developer"],
                "related_keywords": ["Python", "Development"],
                "location": "Sydney",
                "required_skills": ["Python"],
                "experience_years_min": 3
            }

            Query: "Looking for project managers with PMP certification"
            Response: {
                "role": "Project Manager",
                "related_roles": ["Program Manager", "Project Lead"],
                "related_keywords": ["Project Management", "PMP"],
                "location": null,
                "required_skills": ["Project Management", "PMP"],
                "experience_years_min": null
            }
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a search filter extraction assistant. Extract structured search filters from natural language queries."},
                    {"role": "user", "content": f"{prompt}\n\nQuery: {query}"}
                ],
                response_format={ "type": "json_object" }
            )

            # Parse the JSON response
            filters = json.loads(response.choices[0].message.content)
            return filters

        except Exception as e:
            raise Exception(f"Error extracting filters with OpenAI: {str(e)}")

    def rank_candidates(self, recruiter_query: str, candidates: list, top_n: int = 5) -> list:
        """
        Rank candidates based on their relevance to the recruiter's query using OpenAI.
        
        Args:
            recruiter_query (str): The original recruiter query in natural language
            candidates (list): List of candidate dictionaries from Supabase
            top_n (int): Number of top candidates to rank (default: 5)
        
        Returns:
            list: List of ranked candidates with scores and explanations
        """
        try:
            # Take top N candidates
            candidates_to_rank = candidates[:top_n]
            ranked_candidates = []
            
            for candidate in candidates_to_rank:
                # Construct the prompt
                prompt = f"""You are an expert technical recruiter. Based on the following recruiter query:

"{recruiter_query}"

Evaluate this candidate profile:

- Name: {candidate['full_name']}
- Title: {candidate['current_or_last_job_title']}
- Experience: {candidate['total_years_experience']} years
- Skills: {', '.join(candidate['skills'])}
- Location: {candidate['location']}
- Education: {', '.join(candidate.get('education', ['Not provided']))}

Give a relevance score from 0–10 and list 2–3 short bullet points explaining your reasoning.
Format your response as:
Score: [number]
Reasoning:
- [bullet point 1]
- [bullet point 2]
- [bullet point 3]"""

                # Get response from OpenAI
                response = self.client.chat.completions.create(
                    model="gpt-4-turbo-preview",
                    messages=[
                        {"role": "system", "content": "You are an expert technical recruiter evaluating candidate profiles."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                # Parse the response
                response_text = response.choices[0].message.content
                
                # Extract score and reasoning
                score_line = response_text.split('\n')[0]
                score = int(score_line.split(':')[1].strip())
                
                reasoning_lines = response_text.split('Reasoning:')[1].strip().split('\n')
                reasoning = [line.strip('- ').strip() for line in reasoning_lines if line.strip()]
                
                # Add to ranked candidates
                ranked_candidates.append({
                    'candidate': candidate,
                    'score': score,
                    'reasoning': reasoning
                })
            
            # Sort by score in descending order
            ranked_candidates.sort(key=lambda x: x['score'], reverse=True)
            
            return ranked_candidates
            
        except Exception as e:
            logger.error(f"Error ranking candidates: {str(e)}")
            return []

    def generate_outreach(self, candidate, original_query):
        """Generate personalized outreach message and 3 HR screening questions"""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Prepare the prompt
                prompt = f"""As an HR professional, generate a personalized outreach message and 3 highly targeted HR screening questions for this candidate:

Candidate Details:
- Name: {candidate['full_name']}
- Current Role: {candidate['current_or_last_job_title']}
- Years of Experience: {candidate['total_years_experience']}
- Location: {candidate['location']}
- Skills: {', '.join(candidate['skills'])}

Original Query: {original_query}

Please provide:
1. A personalized outreach message that:
   - References their specific experience and skills
   - Mentions the role they're being considered for
   - Is professional but conversational
   - Includes a clear call to action

2. Three highly personalized HR screening questions that:
   - Are specifically tailored to their background and experience
   - Focus on their career progression and motivations
   - Address potential concerns or gaps in their profile
   - Help assess their fit for the specific role mentioned in the query
   - Avoid generic questions that could apply to any candidate

Format the response as JSON with two fields:
{{
    "outreach_message": "the personalized message",
    "screening_questions": ["question1", "question2", "question3"]
}}"""

                # Call OpenAI API with retry logic
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {"role": "system", "content": "You are an experienced HR professional who specializes in candidate outreach and screening. Focus on generating highly personalized questions that are specific to the candidate's background and the role they're being considered for."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"},
                        temperature=0.7,  # Add some creativity while maintaining professionalism
                        max_tokens=1000   # Limit response length
                    )
                except Exception as api_error:
                    logger.error(f"OpenAI API error (attempt {attempt + 1}/{max_retries}): {str(api_error)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                    raise
                
                # Parse the response
                result = json.loads(response.choices[0].message.content)
                
                # Validate the response structure
                if not isinstance(result, dict) or 'outreach_message' not in result or 'screening_questions' not in result:
                    raise ValueError("Invalid response structure from OpenAI API")
                
                if not isinstance(result['screening_questions'], list) or len(result['screening_questions']) != 3:
                    raise ValueError("Invalid screening questions format")
                
                return result
                
            except Exception as e:
                logger.error(f"Error generating outreach (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                
                # Return a fallback response on final failure
                return {
                    "outreach_message": f"Hi {candidate['full_name']},\n\nI came across your profile and was impressed by your experience in {candidate['current_or_last_job_title']}. Your background in {', '.join(candidate['skills'][:3])} aligns well with what we're looking for.\n\nWould you be open to discussing this opportunity further?\n\nBest regards,\n[Your Name]",
                    "screening_questions": [
                        f"Given your experience in {candidate['current_or_last_job_title']}, what aspects of this opportunity interest you most?",
                        f"How has your background in {', '.join(candidate['skills'][:2])} prepared you for this role?",
                        "What are your expectations regarding career growth in this position?"
                    ]
                } 