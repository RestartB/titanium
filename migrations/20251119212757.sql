-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "delete_leavers" boolean NOT NULL DEFAULT false;
