-- Run this entire block in your Supabase SQL editor

CREATE TABLE scans (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  job_title TEXT,
  verdict TEXT,
  risk_level TEXT,
  patterns JSONB,
  eeoc_category TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscribers (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  scan_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "insert scans" ON scans FOR INSERT WITH CHECK (true);
CREATE POLICY "read scans" ON scans FOR SELECT USING (true);
CREATE POLICY "insert subscribers" ON subscribers FOR INSERT WITH CHECK (true);
