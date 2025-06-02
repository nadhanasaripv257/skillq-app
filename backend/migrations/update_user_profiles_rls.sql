-- Ensure RLS is enabled
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Allow insert for authenticated users" ON user_profiles;
DROP POLICY IF EXISTS "Allow read own profile" ON user_profiles;
DROP POLICY IF EXISTS "Allow update own profile" ON user_profiles;

-- Policy to allow authenticated users to insert their own profile
CREATE POLICY "Allow insert for authenticated users"
ON user_profiles
FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Allow reading own profile
CREATE POLICY "Allow read own profile"
ON user_profiles
FOR SELECT
USING (auth.uid() = user_id);

-- Allow updating own profile
CREATE POLICY "Allow update own profile"
ON user_profiles
FOR UPDATE
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id); 