-- Modify "guild_rep_settings" table
ALTER TABLE "guild_rep_settings" ADD COLUMN "delete_leavers" boolean NOT NULL DEFAULT false;
-- Modify "user_rep" table
ALTER TABLE "user_rep" ADD COLUMN "daily_snapshots" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
