-- Add value to enum type: "automodactiontype"
ALTER TYPE "automodactiontype" ADD VALUE 'SEND_MESSAGE';
-- Modify "automod_actions" table
ALTER TABLE "automod_actions" ADD COLUMN "message_content" character varying(2000) NULL, ADD COLUMN "message_reply" boolean NOT NULL DEFAULT false, ADD COLUMN "message_mention" boolean NOT NULL DEFAULT false, ADD COLUMN "message_embed" boolean NOT NULL DEFAULT false, ADD COLUMN "embed_colour" character varying(7) NULL;
-- Modify "bouncer_actions" table
ALTER TABLE "bouncer_actions" DROP COLUMN "message_content", DROP COLUMN "dm_user";
