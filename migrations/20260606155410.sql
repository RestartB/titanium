-- Modify "leaderboard_user_stats" table
ALTER TABLE "leaderboard_user_stats" ADD COLUMN "vc_minutes" bigint NOT NULL DEFAULT 0;
