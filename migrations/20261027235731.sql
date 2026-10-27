-- Modify "guild_limits" table
ALTER TABLE "guild_limits" ADD COLUMN "tag_responses" integer NOT NULL DEFAULT 50;
