-- Rename a constraint from "automod_actions_pkey1" to "automod_actions_pkey"
ALTER TABLE "automod_actions" RENAME CONSTRAINT "automod_actions_pkey1" TO "automod_actions_pkey";
-- Rename a constraint from "automod_rules_pkey1" to "automod_rules_pkey"
ALTER TABLE "automod_rules" RENAME CONSTRAINT "automod_rules_pkey1" TO "automod_rules_pkey";
