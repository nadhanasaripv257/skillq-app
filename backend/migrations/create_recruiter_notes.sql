-- Create recruiter_notes table
CREATE TABLE IF NOT EXISTS recruiter_notes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    recruiter_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES resumes(id) ON DELETE CASCADE,
    outreach_message TEXT,
    screening_questions TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_recruiter_notes_recruiter_id ON recruiter_notes(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_recruiter_notes_candidate_id ON recruiter_notes(candidate_id);

-- Add RLS policies
ALTER TABLE recruiter_notes ENABLE ROW LEVEL SECURITY;

-- Allow users to view their own notes
CREATE POLICY "Users can view their own notes"
    ON recruiter_notes
    FOR SELECT
    USING (auth.uid() = recruiter_id);

-- Allow users to insert their own notes
CREATE POLICY "Users can insert their own notes"
    ON recruiter_notes
    FOR INSERT
    WITH CHECK (auth.uid() = recruiter_id);

-- Allow users to update their own notes
CREATE POLICY "Users can update their own notes"
    ON recruiter_notes
    FOR UPDATE
    USING (auth.uid() = recruiter_id)
    WITH CHECK (auth.uid() = recruiter_id);

-- Allow users to delete their own notes
CREATE POLICY "Users can delete their own notes"
    ON recruiter_notes
    FOR DELETE
    USING (auth.uid() = recruiter_id);

-- Grant access to authenticated users
GRANT ALL ON recruiter_notes TO authenticated; 