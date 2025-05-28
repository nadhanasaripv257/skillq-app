-- Drop existing triggers
DROP TRIGGER IF EXISTS refresh_dashboard_metrics_insert ON resumes;
DROP TRIGGER IF EXISTS refresh_dashboard_metrics_update ON resumes;
DROP TRIGGER IF EXISTS refresh_dashboard_metrics_delete ON resumes;

-- Drop existing function
DROP FUNCTION IF EXISTS refresh_dashboard_metrics();

-- Create a new function that handles permission errors gracefully
CREATE OR REPLACE FUNCTION refresh_dashboard_metrics()
RETURNS TRIGGER AS $$
BEGIN
    BEGIN
        REFRESH MATERIALIZED VIEW CONCURRENTLY dashboard_metrics;
    EXCEPTION WHEN OTHERS THEN
        -- Log the error but don't fail the transaction
        RAISE NOTICE 'Error refreshing dashboard_metrics: %', SQLERRM;
    END;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Recreate triggers
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

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION refresh_dashboard_metrics() TO authenticated;
GRANT TRIGGER ON resumes TO authenticated; 