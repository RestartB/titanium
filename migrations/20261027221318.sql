-- Modify "guild_tag_settings" table
ALTER TABLE "guild_tag_settings" ADD COLUMN "global_ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[], ADD COLUMN "global_ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
-- Modify "tag_quick_responses" table
ALTER TABLE "tag_quick_responses" ADD COLUMN "ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[], ADD COLUMN "ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[];
