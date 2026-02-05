-- Modify "leaderboard_user_stats" table
ALTER TABLE "leaderboard_user_stats" ADD COLUMN "explicit_count" integer NOT NULL DEFAULT 0;
