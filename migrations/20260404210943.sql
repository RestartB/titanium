-- Create "guild_tag_settings" table
CREATE TABLE "guild_tag_settings" (
  "guild_id" bigint NOT NULL,
  "prefix_fallback" boolean NOT NULL DEFAULT true,
  "allow_user_tags" boolean NOT NULL DEFAULT true,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_tag_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create "tags" table
CREATE TABLE "tags" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "owner_id" bigint NOT NULL,
  "is_user" boolean NOT NULL,
  "name" character varying(80) NOT NULL,
  "content" character varying(1024) NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "tags_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_tag_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE
);