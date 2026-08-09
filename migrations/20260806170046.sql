-- Modify "bouncer_actions" table
ALTER TABLE "bouncer_actions" ADD COLUMN "role_ids" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
-- Modify "bouncer_criteria" table
ALTER TABLE "bouncer_criteria" ADD COLUMN "match_all_words" boolean NOT NULL DEFAULT false;
-- Set null rule names to ""
UPDATE "bouncer_rules" SET "rule_name" = '' WHERE "rule_name" IS NULL;
-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" ALTER COLUMN "rule_name" SET NOT NULL, ADD COLUMN "match_all_criteria" boolean NOT NULL DEFAULT true, ADD COLUMN "order" integer NOT NULL DEFAULT 0, ADD COLUMN "stop_if_triggered" boolean NOT NULL DEFAULT false;
