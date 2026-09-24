-- Modify "guild_settings" table
ALTER TABLE "guild_settings" DROP COLUMN "loading_reaction", DROP COLUMN "allow_prefix", DROP COLUMN "blocked_channels", DROP COLUMN "blocked_roles";
-- Modify "guild_tag_settings" table
ALTER TABLE "guild_tag_settings" DROP COLUMN "prefix_fallback";
