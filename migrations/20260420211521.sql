-- Modify "tags" table
ALTER TABLE "tags" ALTER COLUMN "guild_id" DROP NOT NULL, ADD CONSTRAINT "uq_tag_guild_name" UNIQUE ("guild_id", "name");
-- Create index "uq_tag_user_name" to table: "tags"
CREATE UNIQUE INDEX "uq_tag_user_name" ON "tags" ("owner_id", "name") WHERE (is_user = true);
