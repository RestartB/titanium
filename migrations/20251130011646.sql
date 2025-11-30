-- Modify "fireboard_boards" table
ALTER TABLE "fireboard_boards" ALTER COLUMN "id" DROP DEFAULT;
-- Modify "guild_logging_settings" table
ALTER TABLE "guild_logging_settings" ADD COLUMN "titanium_bouncer_trigger_id" bigint NULL;
-- Modify "fireboard_messages" table
ALTER TABLE "fireboard_messages" DROP CONSTRAINT "fireboard_messages_fireboard_id_fkey", ADD CONSTRAINT "fireboard_messages_fireboard_id_fkey" FOREIGN KEY ("fireboard_id") REFERENCES "fireboard_boards" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION;
