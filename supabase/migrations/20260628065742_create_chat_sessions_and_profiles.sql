/*
# FocalPoint: Chat Sessions and User Profile

1. New Tables
   - `chat_sessions`
     - `id` (text, primary key — matches the frontend genId format)
     - `title` (text, the first user message truncated to 40 chars)
     - `messages` (jsonb — full message array: [{role, text, responseId}])
     - `created_at` (timestamptz)
   - `user_profile`
     - `id` (text, primary key — device fingerprint stored in localStorage)
     - `complexity_score` (int, 1–10, default 5)
     - `preferred_format` (text, 'prose' or 'bullets')
     - `topics_to_simplify` (jsonb array)
     - `prospective_flags` (jsonb array)
     - `updated_at` (timestamptz)

2. Security
   - RLS enabled on both tables.
   - Single-tenant (no auth) app: anon + authenticated can read/write all rows.
   - No user_id column — all users share the same namespace (single-device app).

3. Notes
   - `messages` jsonb stores the full conversation so the sidebar can restore it.
   - Keep up to 20 sessions per browser (enforced in frontend, not DB).
   - `user_profile.id` is a stable browser-side key like 'fp_user_default'.
*/

CREATE TABLE IF NOT EXISTS chat_sessions (
  id          text PRIMARY KEY,
  title       text NOT NULL DEFAULT 'Chat',
  messages    jsonb NOT NULL DEFAULT '[]',
  created_at  timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_sessions"  ON chat_sessions;
DROP POLICY IF EXISTS "anon_insert_sessions"  ON chat_sessions;
DROP POLICY IF EXISTS "anon_update_sessions"  ON chat_sessions;
DROP POLICY IF EXISTS "anon_delete_sessions"  ON chat_sessions;

CREATE POLICY "anon_select_sessions" ON chat_sessions FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_sessions" ON chat_sessions FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_sessions" ON chat_sessions FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_sessions" ON chat_sessions FOR DELETE
  TO anon, authenticated USING (true);


CREATE TABLE IF NOT EXISTS user_profile (
  id                  text PRIMARY KEY,
  complexity_score    int NOT NULL DEFAULT 5,
  preferred_format    text NOT NULL DEFAULT 'prose',
  topics_to_simplify  jsonb NOT NULL DEFAULT '[]',
  prospective_flags   jsonb NOT NULL DEFAULT '[]',
  updated_at          timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_profile ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_profile"  ON user_profile;
DROP POLICY IF EXISTS "anon_insert_profile"  ON user_profile;
DROP POLICY IF EXISTS "anon_update_profile"  ON user_profile;
DROP POLICY IF EXISTS "anon_delete_profile"  ON user_profile;

CREATE POLICY "anon_select_profile" ON user_profile FOR SELECT
  TO anon, authenticated USING (true);
CREATE POLICY "anon_insert_profile" ON user_profile FOR INSERT
  TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon_update_profile" ON user_profile FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);
CREATE POLICY "anon_delete_profile" ON user_profile FOR DELETE
  TO anon, authenticated USING (true);
