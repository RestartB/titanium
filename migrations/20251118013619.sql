-- Create enum type "calctype"
CREATE TYPE "calctype" AS ENUM ('FIXED', 'RANDOM', 'LENGTH');
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ADD COLUMN "leaderboard_enabled" boolean NOT NULL DEFAULT false;
-- Create "leaderboard_user_stats" table
CREATE TABLE "leaderboard_user_stats" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "xp" integer NOT NULL DEFAULT 0,
  "level" integer NOT NULL DEFAULT 0,
  "daily_snapshots" integer[] NOT NULL DEFAULT ARRAY[]::integer[],
  PRIMARY KEY ("id")
);
-- Create index "ix_leaderboard_user_stats_guild_id" to table: "leaderboard_user_stats"
CREATE INDEX "ix_leaderboard_user_stats_guild_id" ON "leaderboard_user_stats" ("guild_id");
-- Create index "ix_leaderboard_user_stats_user_id" to table: "leaderboard_user_stats"
CREATE INDEX "ix_leaderboard_user_stats_user_id" ON "leaderboard_user_stats" ("user_id");
-- Create "guild_leaderboard_settings" table
CREATE TABLE "guild_leaderboard_settings" (
  "guild_id" bigint NOT NULL,
  "mode" "calctype" NOT NULL,
  "cooldown" integer NOT NULL DEFAULT 5,
  "base_xp" integer NOT NULL DEFAULT 10,
  "min_xp" integer NOT NULL DEFAULT 15,
  "max_xp" integer NOT NULL DEFAULT 25,
  "xp_mult" double precision NOT NULL DEFAULT 1.0,
  "levelup_notifications" boolean NOT NULL DEFAULT true,
  "notification_channel" bigint NULL,
  "web_leaderboard_enabled" boolean NOT NULL DEFAULT true,
  "web_login_required" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_leaderboard_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "leaderboard_levels" table
CREATE TABLE "leaderboard_levels" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "xp" integer NOT NULL DEFAULT 0,
  "reward_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("id"),
  CONSTRAINT "leaderboard_levels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_leaderboard_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
