-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings" ADD COLUMN "warn_additional" character varying(256) NULL, ADD COLUMN "mute_additional" character varying(256) NULL, ADD COLUMN "kick_additional" character varying(256) NULL, ADD COLUMN "ban_additional" character varying(256) NULL;
