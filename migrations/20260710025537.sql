-- Modify "error_logs" table
ALTER TABLE "error_logs" DROP CONSTRAINT IF EXISTS "error_logs_guild_id_fkey";
ALTER TABLE "error_logs" ALTER COLUMN "guild_id" DROP NOT NULL;
