-- Create enum type "casetype"
CREATE TYPE "casetype" AS ENUM ('WARN', 'MUTE', 'KICK', 'BAN');
-- Create enum type "eventtype"
CREATE TYPE "eventtype" AS ENUM ('MUTE_REFRESH', 'PERMA_MUTE_REFRESH', 'UNBAN');
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ADD COLUMN "delete_after_3_days" boolean NOT NULL DEFAULT true;
-- Modify "mod_cases" table
ALTER TABLE "mod_cases" ALTER COLUMN "type" TYPE "casetype" USING "type"::"casetype";
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ALTER COLUMN "type" TYPE "eventtype" USING "type"::"eventtype";
