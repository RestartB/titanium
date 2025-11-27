-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ALTER COLUMN "base_xp" DROP NOT NULL, ALTER COLUMN "min_xp" DROP NOT NULL, ALTER COLUMN "max_xp" DROP NOT NULL, ALTER COLUMN "xp_mult" DROP NOT NULL;
