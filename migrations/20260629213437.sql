-- Rename a column from "action_type" to "type"
ALTER TABLE "automod_actions" RENAME COLUMN "action_type" TO "type";
-- Rename a column from "criteria_type" to "type"
ALTER TABLE "automod_criteria" RENAME COLUMN "criteria_type" TO "type";
-- Modify "automod_rules" table
ALTER TABLE "automod_rules" ALTER COLUMN "rule_name" SET NOT NULL;
-- Rename a column from "action_type" to "type"
ALTER TABLE "bouncer_actions" RENAME COLUMN "action_type" TO "type";
-- Rename a column from "criteria_type" to "type"
ALTER TABLE "bouncer_criteria" RENAME COLUMN "criteria_type" TO "type";
-- Rename a column from "action_type" to "type"
ALTER TABLE "old_automod_actions" RENAME COLUMN "action_type" TO "type";
-- Modify "old_automod_actions" table
ALTER TABLE "old_automod_actions" ALTER COLUMN "message_reply" SET DEFAULT true, ALTER COLUMN "message_mention" SET DEFAULT true;
