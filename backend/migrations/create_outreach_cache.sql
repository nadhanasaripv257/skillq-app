-- Create outreach_cache table
CREATE TABLE IF NOT EXISTS outreach_cache (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    candidate_id UUID REFERENCES resumes(id) ON DELETE CASCADE,
    query_hash TEXT NOT NULL,
    outreach_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_outreach_cache_candidate_id ON outreach_cache(candidate_id);
CREATE INDEX IF NOT EXISTS idx_outreach_cache_query_hash ON outreach_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_outreach_cache_expires_at ON outreach_cache(expires_at);

-- Add RLS policies
ALTER TABLE outreach_cache ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to view cache
CREATE POLICY "Authenticated users can view cache"
    ON outreach_cache
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow authenticated users to insert cache
CREATE POLICY "Authenticated users can insert cache"
    ON outreach_cache
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Allow authenticated users to update cache
CREATE POLICY "Authenticated users can update cache"
    ON outreach_cache
    FOR UPDATE
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Allow authenticated users to delete cache
CREATE POLICY "Authenticated users can delete cache"
    ON outreach_cache
    FOR DELETE
    TO authenticated
    USING (true);

-- Grant access to authenticated users
GRANT ALL ON outreach_cache TO authenticated;

-- Create function to clean expired cache entries
CREATE OR REPLACE FUNCTION clean_expired_outreach_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM outreach_cache
    WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to clean expired cache entries
CREATE OR REPLACE FUNCTION trigger_clean_expired_outreach_cache()
RETURNS trigger AS $$
BEGIN
    PERFORM clean_expired_outreach_cache();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER clean_expired_outreach_cache_trigger
    AFTER INSERT OR UPDATE ON outreach_cache
    EXECUTE FUNCTION trigger_clean_expired_outreach_cache(); 