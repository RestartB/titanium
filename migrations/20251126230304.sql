-- Modify "leaderboard_user_stats" table
ALTER TABLE "leaderboard_user_stats" ADD CONSTRAINT "uq_leaderboard_guild_user" UNIQUE ("guild_id", "user_id");
