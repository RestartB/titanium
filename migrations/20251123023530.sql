-- Rename a column from "confession_channel_id" to "confessions_channel_id"
ALTER TABLE "guild_confession_settings" RENAME COLUMN "confession_channel_id" TO "confessions_channel_id";
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" DROP COLUMN "confession_enabled", ADD COLUMN "confessions_enabled" boolean NOT NULL DEFAULT false;
