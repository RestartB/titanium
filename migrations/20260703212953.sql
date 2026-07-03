-- Modify "anonymous_poll_responses" table
ALTER TABLE "anonymous_poll_responses" DROP CONSTRAINT "uq_user_poll_id", ADD CONSTRAINT "uq_poll_user_id" UNIQUE ("poll_id", "user_id");
-- Create index "ix_available_webhooks_guild_id" to table: "available_webhooks"
CREATE INDEX "ix_available_webhooks_guild_id" ON "available_webhooks" ("guild_id");
-- Create index "ix_error_logs_guild_id" to table: "error_logs"
CREATE INDEX "ix_error_logs_guild_id" ON "error_logs" ("guild_id", "time_occurred" DESC);
-- Create index "ix_fireboard_messages_fireboard_id" to table: "fireboard_messages"
CREATE INDEX "ix_fireboard_messages_fireboard_id" ON "fireboard_messages" ("fireboard_id");
-- Create index "ix_fireboard_messages_guild_id" to table: "fireboard_messages"
CREATE INDEX "ix_fireboard_messages_guild_id" ON "fireboard_messages" ("guild_id");
-- Create index "ix_game_stats_user_id" to table: "game_stats"
CREATE INDEX "ix_game_stats_user_id" ON "game_stats" ("user_id");
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ADD COLUMN "rep_enabled" boolean NOT NULL DEFAULT true;
-- Drop index "ix_leaderboard_user_stats_guild_id" from table: "leaderboard_user_stats"
DROP INDEX "ix_leaderboard_user_stats_guild_id";
-- Create index "ix_leaderboard_user_stats_guild_xp" to table: "leaderboard_user_stats"
CREATE INDEX "ix_leaderboard_user_stats_guild_xp" ON "leaderboard_user_stats" ("guild_id", "xp" DESC);
-- Create index "ix_mod_case_comments_case_id_guild_id" to table: "mod_case_comments"
CREATE INDEX "ix_mod_case_comments_case_id_guild_id" ON "mod_case_comments" ("case_id", "guild_id");
-- Create index "ix_mod_cases_guild_id" to table: "mod_cases"
CREATE INDEX "ix_mod_cases_guild_id" ON "mod_cases" ("guild_id", "time_created" DESC);
-- Create index "ix_mod_cases_guild_id_user_id" to table: "mod_cases"
CREATE INDEX "ix_mod_cases_guild_id_user_id" ON "mod_cases" ("guild_id", "user_id", "time_created" DESC);
-- Create index "ix_scheduled_tasks_guild_user_type" to table: "scheduled_tasks"
CREATE INDEX "ix_scheduled_tasks_guild_user_type" ON "scheduled_tasks" ("guild_id", "user_id", "type");
-- Create "rep_add_history" table
CREATE TABLE "rep_add_history" (
  "id" uuid NOT NULL,
  "user_id" bigint NOT NULL,
  "target_id" bigint NOT NULL,
  "guild_id" bigint NOT NULL,
  "time" timestamptz NOT NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_rep_add_history_guild_user_target" to table: "rep_add_history"
CREATE INDEX "ix_rep_add_history_guild_user_target" ON "rep_add_history" ("guild_id", "user_id", "target_id");
-- Create "user_rep" table
CREATE TABLE "user_rep" (
  "id" uuid NOT NULL,
  "user_id" bigint NOT NULL,
  "guild_id" bigint NOT NULL,
  "rep" bigint NOT NULL DEFAULT 0,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_user_guild_id" UNIQUE ("user_id", "guild_id")
);
-- Create index "ix_user_rep_guild_rep" to table: "user_rep"
CREATE INDEX "ix_user_rep_guild_rep" ON "user_rep" ("guild_id", "rep" DESC);
-- Create "guild_rep_settings" table
CREATE TABLE "guild_rep_settings" (
  "guild_id" bigint NOT NULL,
  "rep_hint" boolean NOT NULL DEFAULT true,
  "allow_rep_remove" boolean NOT NULL DEFAULT true,
  "web_leaderboard_enabled" boolean NOT NULL DEFAULT true,
  "web_login_required" boolean NOT NULL DEFAULT true,
  "ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  "ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_rep_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE
);
