-- Add new columns if they don't exist
DO $$ 
BEGIN
    -- Add parsed_data column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'resumes' AND column_name = 'parsed_data') THEN
        ALTER TABLE resumes ADD COLUMN parsed_data JSONB;
    END IF;

    -- Add pii column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'resumes' AND column_name = 'pii') THEN
        ALTER TABLE resumes ADD COLUMN pii JSONB;
    END IF;

    -- Add created_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'resumes' AND column_name = 'created_at') THEN
        ALTER TABLE resumes ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW());
    END IF;

    -- Add updated_at column if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                  WHERE table_name = 'resumes' AND column_name = 'updated_at') THEN
        ALTER TABLE resumes ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW());
    END IF;
END $$;

-- Update existing rows with default values for new columns
UPDATE resumes 
SET 
    parsed_data = COALESCE(parsed_data, '{}'::jsonb),
    pii = COALESCE(pii, '{}'::jsonb)
WHERE 
    parsed_data IS NULL 
    OR pii IS NULL;

-- Make new columns NOT NULL
ALTER TABLE resumes 
    ALTER COLUMN parsed_data SET NOT NULL,
    ALTER COLUMN pii SET NOT NULL;

-- Create index on id for faster lookups
CREATE INDEX IF NOT EXISTS idx_resumes_id ON resumes(id);

-- Create or replace the update_updated_at_column function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = TIMEZONE('utc'::text, NOW());
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop existing trigger if it exists
DROP TRIGGER IF EXISTS update_resumes_updated_at ON resumes;

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_resumes_updated_at
    BEFORE UPDATE ON resumes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column(); 