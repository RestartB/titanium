-- Create enum type "leaderboardvccalctype"
CREATE TYPE "leaderboardvccalctype" AS ENUM ('FIXED', 'RANDOM');
-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ADD COLUMN "vc_enabled" boolean NOT NULL DEFAULT false, ADD COLUMN "vc_mode" "leaderboardvccalctype" NOT NULL DEFAULT 'FIXED', ADD COLUMN "vc_delay" integer NOT NULL DEFAULT 5, ADD COLUMN "vc_base_xp" integer NULL DEFAULT 10, ADD COLUMN "vc_min_xp" integer NULL DEFAULT 15, ADD COLUMN "vc_max_xp" integer NULL DEFAULT 25;
