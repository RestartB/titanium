-- Modify "mod_case_comments" table
ALTER TABLE "mod_case_comments" ALTER COLUMN "time_created" SET DEFAULT now();
-- Modify "mod_cases" table
ALTER TABLE "mod_cases" ALTER COLUMN "time_created" SET DEFAULT now();
