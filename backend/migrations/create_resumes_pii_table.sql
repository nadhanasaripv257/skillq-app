-- Create the resumes_pii table
CREATE TABLE resumes_pii (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- Create indexes for faster lookups
CREATE INDEX idx_resumes_pii_resume_id ON resumes_pii(resume_id);
CREATE INDEX idx_resumes_pii_email ON resumes_pii(email);

-- Enable Row Level Security
ALTER TABLE resumes_pii ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Enable read access for authenticated users" ON resumes_pii
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Enable insert access for authenticated users" ON resumes_pii
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

CREATE POLICY "Enable update access for authenticated users" ON resumes_pii
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Create trigger for updated_at
CREATE TRIGGER update_resumes_pii_updated_at
    BEFORE UPDATE ON resumes_pii
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 