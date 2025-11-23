-- Modify "guild_confession_settings" table
ALTER TABLE "guild_confession_settings" DROP COLUMN "confession_log_channel_id", ADD COLUMN "confessions_in_channel" boolean NOT NULL DEFAULT true;
-- Modify "guild_logging_settings" table
ALTER TABLE "guild_logging_settings" ADD COLUMN "titanium_confession_id" bigint NULL;
-- Modify "mod_cases" table
ALTER TABLE "mod_cases" DROP COLUMN "proof_msg_id", DROP COLUMN "proof_channel_id", DROP COLUMN "proof_text";
