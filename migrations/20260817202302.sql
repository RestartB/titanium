-- Add value to enum type: "automodactiontype"
ALTER TYPE "automodactiontype" ADD VALUE 'REACTION';
-- Modify "automod_actions" table
ALTER TABLE "automod_actions" ADD COLUMN "reaction" character varying NULL;
