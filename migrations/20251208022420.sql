-- Modify "guild_logging_settings" table
ALTER TABLE "guild_logging_settings" ADD COLUMN "guild_features_update_id" bigint NULL;
-- Create "opt_out_ids" table
CREATE TABLE "opt_out_ids" (
  "id" bigserial NOT NULL,
  PRIMARY KEY ("id")
);
