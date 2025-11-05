-- Modify "guild_limits" table
ALTER TABLE "guild_limits" ADD COLUMN "bouncer_rules" integer NOT NULL, ADD COLUMN "fireboards" integer NOT NULL, ADD COLUMN "server_counters" integer NOT NULL;
