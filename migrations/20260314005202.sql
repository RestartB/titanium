-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "notification_ping" boolean NOT NULL DEFAULT true;
