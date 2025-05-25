python backend/test_resume_processor.py
zsh: command not found: python-- Add new columns to the resumes table
ALTER TABLE resumes
ADD COLUMN IF NOT EXISTS experience JSONB DEFAULT '[]',
ADD COLUMN IF NOT EXISTS companies TEXT[] DEFAULT '{}',
ADD COLUMN IF NOT EXISTS location TEXT,
ADD COLUMN IF NOT EXISTS additional_info JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS pii JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS file_path TEXT;

-- Create an index on file_path for faster lookups
CREATE INDEX IF NOT EXISTS idx_resumes_file_path ON resumes(file_path);

-- Update the updated_at column to be automatically updated
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

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Resumes are accessible by authenticated users" ON storage.objects;
DROP POLICY IF EXISTS "Resumes can be uploaded by authenticated users" ON storage.objects;
DROP POLICY IF EXISTS "Users can view their own resumes" ON resumes;
DROP POLICY IF EXISTS "Users can insert their own resumes" ON resumes;
DROP POLICY IF EXISTS "Users can update their own resumes" ON resumes;

-- Set up storage policies
CREATE POLICY "Resumes are accessible by authenticated users"
ON storage.objects FOR SELECT
TO authenticated
USING (bucket_id = 'resumes');

CREATE POLICY "Resumes can be uploaded by authenticated users"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'resumes');

-- Enable Row Level Security if not already enabled
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;

-- Create policies for the resumes table
CREATE POLICY "Users can view their own resumes"
ON resumes FOR SELECT
TO authenticated
USING (true);

CREATE POLICY "Users can insert their own resumes"
ON resumes FOR INSERT
TO authenticated
WITH CHECK (true);

CREATE POLICY "Users can update their own resumes"
ON resumes FOR UPDATE
TO authenticated
USING (true)
WITH CHECK (true); 