-- Modify "guild_confession_settings" table
ALTER TABLE "guild_confession_settings" ADD COLUMN "polls_enabled" boolean NOT NULL DEFAULT true;
-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" ALTER COLUMN "base_xp" SET NOT NULL, ALTER COLUMN "min_xp" SET NOT NULL, ALTER COLUMN "max_xp" SET NOT NULL, ALTER COLUMN "xp_mult" SET NOT NULL, ALTER COLUMN "vc_base_xp" SET NOT NULL, ALTER COLUMN "vc_min_xp" SET NOT NULL, ALTER COLUMN "vc_max_xp" SET NOT NULL;
-- Create "anonymous_polls" table
CREATE TABLE "anonymous_polls" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "creator_id" bigint NOT NULL,
  "content" character varying(1000) NOT NULL,
  "answers" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "closing_time" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "anonymous_polls_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create "anonymous_poll_responses" table
CREATE TABLE "anonymous_poll_responses" (
  "id" uuid NOT NULL,
  "user_id" bigint NOT NULL,
  "poll_id" uuid NOT NULL,
  "answer_index" integer NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_user_poll_id" UNIQUE ("user_id", "poll_id"),
  CONSTRAINT "anonymous_poll_responses_poll_id_fkey" FOREIGN KEY ("poll_id") REFERENCES "anonymous_polls" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
