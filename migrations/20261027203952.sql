-- Create "tag_quick_responses" table
CREATE TABLE "tag_quick_responses" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "tag_id" uuid NULL,
  "keywords" character varying(25)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL DEFAULT true,
  "case_sensitive" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "tag_quick_responses_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_tag_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE,
  CONSTRAINT "tag_quick_responses_tag_id_fkey" FOREIGN KEY ("tag_id") REFERENCES "tags" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
