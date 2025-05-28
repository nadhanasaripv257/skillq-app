-- First, ensure the postgres role has proper permissions
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Then grant permissions to authenticated role
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO authenticated;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO authenticated;

-- Grant specific permissions for the dashboard metrics view and its refresh function
GRANT EXECUTE ON FUNCTION refresh_dashboard_metrics() TO authenticated;
GRANT TRIGGER ON resumes TO authenticated;

-- Ensure the materialized view is owned by postgres
ALTER MATERIALIZED VIEW dashboard_metrics OWNER TO postgres;

-- Grant permissions on the resumes table specifically
GRANT ALL ON resumes TO authenticated;
GRANT ALL ON resumes TO public; 