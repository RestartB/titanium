-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings"
ADD COLUMN "external_cases" boolean NOT NULL DEFAULT true,
    ADD COLUMN "external_case_dms" boolean NOT NULL DEFAULT false;
-- Modify "guild_settings" table
ALTER TABLE "guild_settings"
ADD COLUMN "dashboard_managers" bigint [] NOT NULL DEFAULT '{}',
    ADD COLUMN "case_managers" bigint [] NOT NULL DEFAULT '{}';