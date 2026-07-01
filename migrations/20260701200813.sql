-- Modify "guild_limits" table
ALTER TABLE "guild_limits" ALTER COLUMN "automod_rules" SET DEFAULT 10;
-- Change existing limmits
UPDATE "guild_limits" SET "automod_rules" = 10 WHERE "automod_rules" = 50;