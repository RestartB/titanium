-- Modify "guild_automod_settings" table
ALTER TABLE "guild_automod_settings" ADD COLUMN "global_ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[], ADD COLUMN "global_ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
