# SkillQ - Product Requirements Document

## 1. App Overview & Objectives

**SkillQ** is an AI-powered talent search and screening assistant designed for in-house recruiters and hiring managers across tech and non-tech companies. The platform enables recruiters to perform natural-language queries and instantly receive ranked candidate matches with parsed skills, auto-screening, and personalized outreach messages — all while protecting personally identifiable information (PII).

**Primary Objective:**
Reduce the average time-to-hire from 60+ days to just minutes through intelligent automation, eliminating manual sourcing, inefficient screening, and human bias.

---

## 2. Target Audience

* **Primary Users:**

  * In-house recruiters
  * Hiring managers

* **Industries:**

  * Both tech and non-tech companies

* **Usage Environment:**

  * Internal use only (not client-facing in MVP)
  * Used by individuals or small hiring teams via web application

---

## 3. Core Features & Functionality

### ✅ Natural Language Search ("PeopleGPT")

* Recruiters can input plain-English hiring requests.
* AI interprets query, breaks down into structured filters.

### ✅ Conversational Refinement

* SkillQ asks clarifying questions to improve search accuracy.
* Recruiters can tweak filters dynamically.

### ✅ Resume Parsing & Skill Extraction

* Uploads accepted: PDF, DOCX, LinkedIn URL
* System extracts relevant information (titles, skills, experience, location).
* Parsing respects PII boundaries (see Security).

### ✅ Candidate Ranking Engine

* Scores candidates based on recruiter query.
* Sorts by relevance and confidence.
* Includes transparent “Why this match?” explanation.

### ✅ Personalized Outreach Messaging

* Auto-generates tailored outreach emails/messages.
* Recruiter can edit before sending.

### ✅ AI-Based Screening Questions

* Generates dynamic screening Q\&A for top candidates.
* Helps with early-stage vetting.

---

## 4. User Interface Design Flow

### 1. **Login Dashboard**

* Upload resumes or LinkedIn URLs.
* Start a new query.

### 2. **Query Interface**

* Input free-text prompt.
* See live suggestions.
* System may prompt for clarification.

### 3. **Search Results Page**

* List of ranked candidates.
* View skills, resume summary, confidence match score.
* Options: View full profile, edit query, or send outreach.

### 4. **Messaging & Screening**

* Outreach message generator.
* View or customize pre-screening questions.
* Export or tag candidates for internal tracking.

---

## 5. Security Considerations

* **PII Protection** (MVP Priority):

  * No names, emails, phone numbers, LinkedIn URLs sent to external LLMs.
  * Resume parsing occurs locally or with anonymized content.
  * Optional enterprise deployment for full data control.

* **Data Ownership:**

  * Companies retain ownership of uploaded resumes and candidate data.
  * GDPR and global privacy compliance is planned.

---

## 6. Potential Challenges & Solutions

| Challenge                   | Solution                                               |
| --------------------------- | ------------------------------------------------------ |
| Diverse resume formats      | Use resilient parsers with fallbacks                   |
| Ambiguous recruiter queries | Implement clarification prompts via chat               |
| PII in LLM calls            | Anonymize before processing; restrict external API use |
| Varying role vocabularies   | Train context models across industries                 |

---

## 7. Future Expansion Possibilities

* **Talent Pool Insights Dashboard**
  Visual dashboards for hiring trends, skill gaps, sourcing performance.

* **Diversity Scoring**
  AI-generated DEI metrics (gender-neutral, geography-based only).

* **ATS & CRM Integrations**
  Direct sync with Greenhouse, Lever, etc.

* **Calendar + Interview Coordination**
  AI-assisted scheduling based on availability.

* **Multi-user Collaboration Tools**
  Commenting, sharing, and candidate shortlist tracking.

---

## 8. Success Metrics (MVP Phase)

* Average query-to-shortlist time: < 5 minutes
* Resume parse accuracy: > 90%
* Recruiter satisfaction score (NPS): > 60
* Reduction in manual screening hours: > 50%

---

## 9. Tech Stack Recommendation (MVP-friendly)

* **Frontend:** Web App (React or Streamlit for quick prototyping)
* **Backend:** Python API (FastAPI/Flask) with local resume processing
* **AI/NLP:** OpenAI/Anthropic API (anonymized inputs only), spaCy
* **Storage:** PostgreSQL + S3 for secure resume uploads
* **Security:** Tokenized user sessions, data encryption at rest & transit

---
