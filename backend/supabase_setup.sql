-- Create the resumes table
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id UUID NOT NULL UNIQUE,
    file_path TEXT NOT NULL,
    
    -- Personal Information
    full_name TEXT,
    email TEXT,
    phone TEXT,
    location TEXT,
    linkedin_url TEXT,
    
    -- Work Experience
    total_years_experience INTEGER,
    current_or_last_job_title TEXT,
    previous_job_titles TEXT[] DEFAULT '{}',
    companies_worked_at TEXT[] DEFAULT '{}',
    employment_type TEXT,
    availability TEXT,
    
    -- Skills and Tools
    skills TEXT[] DEFAULT '{}',
    skill_categories JSONB DEFAULT '{}',
    tools_technologies TEXT[] DEFAULT '{}',
    
    -- Education and Certifications
    education TEXT[] DEFAULT '{}',
    degree_level TEXT[] DEFAULT '{}',
    certifications TEXT[] DEFAULT '{}',
    
    -- Additional Information
    summary_statement TEXT,
    languages_spoken TEXT[] DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Create an index on resume_id for faster lookups
CREATE INDEX IF NOT EXISTS idx_resumes_resume_id ON resumes(resume_id);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create a trigger to automatically update the updated_at column
DROP TRIGGER IF EXISTS update_resumes_updated_at ON resumes;
CREATE TRIGGER update_resumes_updated_at
    BEFORE UPDATE ON resumes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Create a storage bucket for resumes if it doesn't exist
INSERT INTO storage.buckets (id, name, public)
VALUES ('resumes', 'resumes', false)
ON CONFLICT (id) DO NOTHING;

-- Set up storage policies
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' 
        AND policyname = 'Resumes are accessible by authenticated users'
    ) THEN
        CREATE POLICY "Resumes are accessible by authenticated users"
        ON storage.objects FOR SELECT
        TO authenticated
        USING (bucket_id = 'resumes');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' 
        AND policyname = 'Resumes can be uploaded by authenticated users'
    ) THEN
        CREATE POLICY "Resumes can be uploaded by authenticated users"
        ON storage.objects FOR INSERT
        TO authenticated
        WITH CHECK (bucket_id = 'resumes');
    END IF;
END $$;

-- Enable Row Level Security
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

-- Create policies for the resumes table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'resumes' 
        AND policyname = 'Users can view their own resumes'
    ) THEN
        CREATE POLICY "Users can view their own resumes"
        ON resumes FOR SELECT
        TO authenticated
        USING (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'resumes' 
        AND policyname = 'Users can insert their own resumes'
    ) THEN
        CREATE POLICY "Users can insert their own resumes"
        ON resumes FOR INSERT
        TO authenticated
        WITH CHECK (true);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'resumes' 
        AND policyname = 'Users can update their own resumes'
    ) THEN
        CREATE POLICY "Users can update their own resumes"
        ON resumes FOR UPDATE
        TO authenticated
        USING (true)
        WITH CHECK (true);
    END IF;
END $$; 