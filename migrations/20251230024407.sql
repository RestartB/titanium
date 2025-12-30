-- Rename enum type "servercountertype" to "servercountertype_old"
ALTER TYPE "servercountertype" RENAME TO "servercountertype_old";
-- Create enum type "servercountertype"
CREATE TYPE "servercountertype" AS ENUM ('TOTAL_MEMBERS', 'USERS', 'BOTS', 'ONLINE_MEMBERS', 'OFFLINE_MEMBERS', 'CHANNELS', 'CATEGORIES', 'ROLES', 'TOTAL_XP');
-- Alter table "guild_server_counter_channels" to use new enum type
ALTER TABLE "server_counter_channels" ALTER COLUMN count_type TYPE "servercountertype" USING count_type::text::"servercountertype";
-- Drop old enum type "servercountertype_old"
DROP TYPE "servercountertype_old";