-- Create enum type "gametypes"
CREATE TYPE "gametypes" AS ENUM ('DICE', 'COIN');
-- Modify "game_stats" table
ALTER TABLE "game_stats" DROP COLUMN "game_id", DROP COLUMN "played", DROP COLUMN "win", ADD COLUMN "game" "gametypes" NOT NULL, ADD COLUMN "won" boolean NOT NULL;
-- Modify "guild_logging_settings" table
ALTER TABLE "guild_logging_settings" DROP COLUMN "thread_remove_id";
-- Drop "games" table
DROP TABLE "games";
