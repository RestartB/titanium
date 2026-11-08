-- Add value to enum type: "bouncercriteriatype"
ALTER TYPE "bouncercriteriatype" ADD VALUE 'VERIFIED';
-- Create "user_limit_overrides" table
CREATE TABLE "user_limit_overrides" (
  "id" bigserial NOT NULL,
  "tags" integer NOT NULL DEFAULT 250,
  PRIMARY KEY ("id")
);
