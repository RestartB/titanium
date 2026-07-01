-- Modify "guild_automod_settings" table
ALTER TABLE "guild_automod_settings" ADD COLUMN "show_outcome_message" boolean NOT NULL DEFAULT true;
