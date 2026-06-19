-- Modify "guild_confession_settings" table
ALTER TABLE "guild_confession_settings" ADD COLUMN "attachments_allowed" boolean NOT NULL DEFAULT false;
