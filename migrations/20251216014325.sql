-- Modify "leaderboard_user_stats" table
ALTER TABLE "leaderboard_user_stats" ADD COLUMN "message_count" integer NOT NULL DEFAULT 0, ADD COLUMN "word_count" integer NOT NULL DEFAULT 0, ADD COLUMN "attachment_count" integer NOT NULL DEFAULT 0;
