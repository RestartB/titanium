-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" ADD COLUMN "member_join" boolean NOT NULL DEFAULT true, ADD COLUMN "member_update" boolean NOT NULL DEFAULT false, ADD COLUMN "suspicious_reaction" boolean NOT NULL DEFAULT false;
-- Set "member_update" based on evaluate for existing members option
UPDATE "bouncer_rules" SET "member_update" = true WHERE "evaluate_for_existing_members" = true;
-- Drop evaluate_for_existing_members
ALTER TABLE "bouncer_rules" DROP COLUMN "evaluate_for_existing_members";