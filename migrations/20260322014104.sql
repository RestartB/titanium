-- Modify "error_logs" table
ALTER TABLE "error_logs" ALTER COLUMN "time_occurred" TYPE timestamptz;
-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings" DROP COLUMN "external_case_dms";
-- Modify "mod_case_comments" table
ALTER TABLE "mod_case_comments" ALTER COLUMN "time_created" TYPE timestamptz;
-- Modify "mod_cases" table
ALTER TABLE "mod_cases" ALTER COLUMN "time_created" TYPE timestamptz, ALTER COLUMN "time_updated" TYPE timestamptz, ALTER COLUMN "time_expires" TYPE timestamptz;
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ALTER COLUMN "time_scheduled" TYPE timestamptz;
-- Modify "spotify_tokens" table
ALTER TABLE "spotify_tokens" ALTER COLUMN "time_added" TYPE timestamptz;
