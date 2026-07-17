-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "bot_message_tracking" boolean NOT NULL DEFAULT true, ADD COLUMN "bot_message_xp" boolean NOT NULL DEFAULT false, ADD COLUMN "bot_vc_tracking" boolean NOT NULL DEFAULT true, ADD COLUMN "bot_vc_xp" boolean NOT NULL DEFAULT false;
