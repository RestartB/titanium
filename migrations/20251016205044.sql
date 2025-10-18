-- Create "error_logs" table
CREATE TABLE "error_logs" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "module" character varying(100) NOT NULL,
  "error" character varying(512) NOT NULL,
  "details" character varying(1024) NULL,
  "time_occurred" timestamp NOT NULL,
  PRIMARY KEY ("id")
);
