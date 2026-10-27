-- Modify "tags" table
ALTER TABLE "tags" ADD COLUMN "colour" character varying(7) NOT NULL DEFAULT '#979C9F', ADD COLUMN "spoiler" boolean NOT NULL DEFAULT false;
