-- Drop the existing table if it exists
DROP TABLE IF EXISTS resumes CASCADE;

-- Create the resumes table with all necessary columns
CREATE TABLE resumes (
    -- Primary key and file information
    id UUID PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Personal Information
    full_name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    state TEXT,
    country TEXT,
    linkedin_url TEXT,
    
    -- Work Experience
    total_years_experience INTEGER,
    current_or_last_job_title TEXT,
    previous_job_titles TEXT[] NOT NULL DEFAULT '{}',
    companies_worked_at TEXT[] NOT NULL DEFAULT '{}',
    employment_type TEXT,
    availability TEXT,
    
    -- Skills and Tools
    skills TEXT[] NOT NULL DEFAULT '{}',
    skill_categories JSONB NOT NULL DEFAULT '{}',
    tools_technologies TEXT[] NOT NULL DEFAULT '{}',
    
    -- Education and Certifications
    education TEXT[] NOT NULL DEFAULT '{}',
    degree_level TEXT[] NOT NULL DEFAULT '{}',
    certifications TEXT[] NOT NULL DEFAULT '{}',
    
    -- Additional Information
    summary_statement TEXT,
    languages_spoken TEXT[] NOT NULL DEFAULT '{}',
    
    -- Raw and Processed Data
    content TEXT,
    parsed_data JSONB NOT NULL DEFAULT '{}',
    pii JSONB NOT NULL DEFAULT '{}',
    search_blob TEXT,
    issues TEXT[] DEFAULT '{}',
    risk_score INTEGER DEFAULT 0,
    
    -- Metadata
    uploaded_by TEXT NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Create indexes for faster lookups
CREATE INDEX idx_resumes_id ON resumes(id);
CREATE INDEX idx_resumes_file_name ON resumes(file_name);
CREATE INDEX idx_resumes_email ON resumes(email);
CREATE INDEX idx_resumes_location ON resumes(location);
CREATE INDEX idx_resumes_skills ON resumes USING GIN (skills);
CREATE INDEX idx_resumes_companies ON resumes USING GIN (companies_worked_at);
CREATE INDEX idx_resumes_education ON resumes USING GIN (education);
CREATE INDEX idx_resumes_certifications ON resumes USING GIN (certifications);

-- Additional indexes for search optimization
CREATE INDEX idx_resumes_job_title ON resumes(current_or_last_job_title);
CREATE INDEX idx_resumes_experience ON resumes(total_years_experience);
CREATE INDEX idx_resumes_location_lower ON resumes(lower(location));
CREATE INDEX idx_resumes_job_title_lower ON resumes(lower(current_or_last_job_title));

-- Enable Row Level Security
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

-- Create a policy that allows all operations (modify as needed)
CREATE POLICY "Allow all operations" ON resumes
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_resumes_updated_at
    BEFORE UPDATE ON resumes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
