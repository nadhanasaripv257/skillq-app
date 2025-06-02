-- Clean up: Drop ALL existing policies
DROP POLICY IF EXISTS "Users can view their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can insert their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update their own profile" ON user_profiles;
DROP POLICY IF EXISTS "Allow insert for authenticated users" ON user_profiles;
DROP POLICY IF EXISTS "Allow read own profile" ON user_profiles;
DROP POLICY IF EXISTS "Allow update own profile" ON user_profiles;
DROP POLICY IF EXISTS "Allow insert where auth.uid = user_id" ON user_profiles;
DROP POLICY IF EXISTS "Allow insert" ON user_profiles;
DROP POLICY IF EXISTS "Allow read" ON user_profiles;
DROP POLICY IF EXISTS "Allow update" ON user_profiles;

-- Re-enable RLS
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- Add minimal secure policies
-- Allow insert by authenticated user if user_id matches their UID
CREATE POLICY "Allow insert"
ON user_profiles
FOR INSERT
TO authenticated
WITH CHECK (auth.uid() = user_id);

-- Allow read by authenticated user if user_id matches
CREATE POLICY "Allow read"
ON user_profiles
FOR SELECT
TO authenticated
USING (auth.uid() = user_id);

-- Allow update by authenticated user if user_id matches
CREATE POLICY "Allow update"
ON user_profiles
FOR UPDATE
TO authenticated
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id); 