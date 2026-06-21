-- Modify "anonymous_polls" table
ALTER TABLE "anonymous_polls" ADD COLUMN "show_live_results" boolean NOT NULL DEFAULT true;