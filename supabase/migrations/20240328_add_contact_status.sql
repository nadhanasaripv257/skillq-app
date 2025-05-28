-- Add contact_status and follow_up fields to recruiter_notes table
ALTER TABLE recruiter_notes
ADD COLUMN contact_status BOOLEAN DEFAULT FALSE,
ADD COLUMN follow_up_required BOOLEAN DEFAULT FALSE,
ADD COLUMN follow_up_date TIMESTAMP WITH TIME ZONE;

-- Add comment to explain the fields
COMMENT ON COLUMN recruiter_notes.contact_status IS 'Indicates whether the recruiter has contacted the candidate';
COMMENT ON COLUMN recruiter_notes.follow_up_required IS 'Indicates whether a follow-up is required';
COMMENT ON COLUMN recruiter_notes.follow_up_date IS 'Date when follow-up should be done'; 