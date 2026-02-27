-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings" DROP COLUMN "immune_roles", ADD COLUMN "ban_days" integer NOT NULL DEFAULT 0;
