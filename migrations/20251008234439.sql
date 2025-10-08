-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ADD COLUMN "confession_enabled" boolean NOT NULL;
-- Create "guild_confession_settings" table
CREATE TABLE "guild_confession_settings" (
  "guild_id" bigint NOT NULL,
  "confession_channel_id" bigint NULL,
  "confession_log_channel_id" bigint NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_confession_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
