-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ADD COLUMN "tags_enabled" boolean NOT NULL DEFAULT false;
