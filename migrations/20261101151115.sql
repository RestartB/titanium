-- Modify "tag_quick_responses" table
ALTER TABLE "tag_quick_responses" ADD COLUMN "reply" boolean NOT NULL DEFAULT true;
