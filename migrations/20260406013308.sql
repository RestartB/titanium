-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[], ADD COLUMN "ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
