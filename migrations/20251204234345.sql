-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" ADD COLUMN "evaluate_for_existing_members" boolean NOT NULL DEFAULT true;
