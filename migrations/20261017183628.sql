-- Modify "tags" table
ALTER TABLE "tags" ADD COLUMN "components" jsonb[] NOT NULL DEFAULT ARRAY[]::jsonb[];
