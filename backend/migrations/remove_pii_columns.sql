-- Remove PII columns from resumes table
ALTER TABLE resumes
    DROP COLUMN IF EXISTS full_name,
    DROP COLUMN IF EXISTS email,
    DROP COLUMN IF EXISTS phone;

-- Drop related indexes
DROP INDEX IF EXISTS idx_resumes_email;

-- Drop existing materialized view and its dependencies
DROP MATERIALIZED VIEW IF EXISTS dashboard_metrics;
DROP FUNCTION IF EXISTS refresh_dashboard_metrics() CASCADE;
DROP TRIGGER IF EXISTS refresh_dashboard_metrics_trigger ON resumes;

-- Create the new regular view
CREATE OR REPLACE VIEW dashboard_metrics AS
WITH 
-- Get job title counts
job_title_stats AS (
    SELECT 
        current_or_last_job_title,
        COUNT(*) as count
    FROM resumes
    WHERE current_or_last_job_title IS NOT NULL
    GROUP BY current_or_last_job_title
),
-- Get location counts
location_stats AS (
    SELECT 
        location,
        COUNT(*) as count
    FROM resumes
    WHERE location IS NOT NULL
    GROUP BY location
),
-- Get skill counts
skill_stats AS (
    SELECT 
        unnest(skills) as skill,
        COUNT(*) as count
    FROM resumes
    WHERE skills IS NOT NULL AND skills != '{}'
    GROUP BY skill
),
-- Get recent candidates
recent_candidates AS (
    SELECT 
        r.id,
        rp.full_name,
        r.current_or_last_job_title,
        r.location,
        r.created_at
    FROM resumes r
    LEFT JOIN resumes_pii rp ON r.id = rp.resume_id
    ORDER BY r.created_at DESC
    LIMIT 5
)
SELECT
    -- Total candidates
    (SELECT COUNT(*) FROM resumes) as total_candidates,
    
    -- Job title metrics
    (SELECT jsonb_object_agg(current_or_last_job_title, count)
     FROM job_title_stats) as job_title_counts,
    
    -- Location metrics
    (SELECT jsonb_object_agg(location, count)
     FROM location_stats) as location_counts,
    
    -- Skills metrics
    (SELECT jsonb_object_agg(skill, count)
     FROM skill_stats) as skill_counts,
    
    -- Recent candidates
    (SELECT jsonb_agg(
        jsonb_build_object(
            'id', id,
            'full_name', full_name,
            'current_or_last_job_title', current_or_last_job_title,
            'location', location,
            'created_at', created_at
        )
    )
    FROM recent_candidates) as recent_candidates;

-- Grant access to the view
GRANT SELECT ON dashboard_metrics TO authenticated; 