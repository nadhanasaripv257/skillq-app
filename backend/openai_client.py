import os
from openai import OpenAI
from typing import Dict, List
import json

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
            """

            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are a resume parsing assistant. Extract structured information from resume text. Be precise and accurate in your extraction."},
                    {"role": "user", "content": f"{prompt}\n\nResume text:\n{resume_text}"}
                ],
                response_format={ "type": "json_object" }
            )

            # Parse the JSON response
            parsed_data = json.loads(response.choices[0].message.content)
            return parsed_data

        except Exception as e:
            raise Exception(f"Error parsing resume with OpenAI: {str(e)}")

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