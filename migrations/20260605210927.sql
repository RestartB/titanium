-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "stack_roles" boolean NOT NULL DEFAULT true;
