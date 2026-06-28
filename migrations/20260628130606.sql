-- Create enum type "automodcriteriatype"
CREATE TYPE "automodcriteriatype" AS ENUM ('WORD_LIST', 'MALICIOUS_LINK', 'PHISHING_LINK', 'MESSAGE_SPAM', 'MENTION_SPAM', 'WORD_SPAM', 'NEWLINE_SPAM', 'LINK_SPAM', 'ATTACHMENT_SPAM', 'EMOJI_SPAM');
-- Modify "automod_actions" table
ALTER TABLE "automod_actions" DROP COLUMN "role_id", ADD COLUMN "role_ids" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
-- Create "automod_rules" table
CREATE TABLE "automod_rules" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "rule_name" character varying(100) NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "evaluate_edits" boolean NOT NULL DEFAULT true,
  "match_all_criteria" boolean NOT NULL DEFAULT true,
  "order" integer NOT NULL,
  "stop_if_triggered" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "automod_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create "automod_criteria" table
CREATE TABLE "automod_criteria" (
  "id" bigserial NOT NULL,
  "rule_id" uuid NOT NULL,
  "criteria_type" "automodcriteriatype" NOT NULL,
  "threshold" integer NULL,
  "duration" integer NULL,
  "words" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL DEFAULT false,
  "case_sensitive" boolean NOT NULL DEFAULT false,
  "match_all_words" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "automod_criteria_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "automod_rules" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Rename a constraint from "automod_rules_pkey" to "old_automod_rules_pkey"
ALTER TABLE "old_automod_rules" RENAME CONSTRAINT "automod_rules_pkey" TO "old_automod_rules_pkey";
-- Modify "old_automod_rules" table
ALTER TABLE "old_automod_rules" DROP CONSTRAINT "automod_rules_guild_id_fkey", ADD CONSTRAINT "old_automod_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
