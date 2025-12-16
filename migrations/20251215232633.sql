-- Add value to enum type: "eventtype"
ALTER TYPE "eventtype" ADD VALUE 'CLOSE_MUTE' AFTER 'PERMA_MUTE_REFRESH';
-- Modify "fireboard_messages" table
ALTER TABLE "fireboard_messages" DROP COLUMN "channel_id";
-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ALTER COLUMN "mode" SET DEFAULT 'FIXED';
