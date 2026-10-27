-- Create "tag_edit_links" table
CREATE TABLE "tag_edit_links" (
  "page_key" uuid NOT NULL,
  "submit_key" uuid NOT NULL,
  "initial_passed" boolean NOT NULL DEFAULT false,
  "expires_at" timestamptz NOT NULL,
  "user_id" bigint NOT NULL,
  "guild_id" bigint NULL,
  "tag_id" uuid NULL,
  PRIMARY KEY ("page_key"),
  CONSTRAINT "tag_edit_links_tag_id_fkey" FOREIGN KEY ("tag_id") REFERENCES "tags" ("id") ON UPDATE NO ACTION ON DELETE CASCADE
);
