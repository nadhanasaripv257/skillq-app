-- Drop the existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS dashboard_metrics;

-- Create a materialized view for dashboard metrics
CREATE MATERIALIZED VIEW dashboard_metrics AS
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
        id,
        full_name,
        current_or_last_job_title,
        location,
        created_at
    FROM resumes
    ORDER BY created_at DESC
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

-- Create indexes for faster access
CREATE INDEX idx_dashboard_metrics_total ON dashboard_metrics (total_candidates);

-- Create a function to refresh the materialized view
CREATE OR REPLACE FUNCTION refresh_dashboard_metrics()
RETURNS TRIGGER AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_metrics;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create triggers to refresh the view when resumes are modified
CREATE TRIGGER refresh_dashboard_metrics_insert
    AFTER INSERT ON resumes
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_dashboard_metrics();

CREATE TRIGGER refresh_dashboard_metrics_update
    AFTER UPDATE ON resumes
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_dashboard_metrics();

CREATE TRIGGER refresh_dashboard_metrics_delete
    AFTER DELETE ON resumes
    FOR EACH STATEMENT
    EXECUTE FUNCTION refresh_dashboard_metrics();

-- Grant access to the view
GRANT SELECT ON dashboard_metrics TO authenticated; 