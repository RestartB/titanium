-- Add value to enum type: "eventtype"
ALTER TYPE "eventtype" ADD VALUE 'REMINDER';
-- Create "reminders" table
CREATE TABLE "reminders" (
  "id" uuid NOT NULL,
  "guild_id" bigint NULL,
  "channel_id" bigint NULL,
  "user_id" bigint NOT NULL,
  "dm" boolean NOT NULL,
  "time" timestamptz NOT NULL,
  "content" character varying NOT NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_reminders_guild_id" to table: "reminders"
CREATE INDEX "ix_reminders_guild_id" ON "reminders" ("guild_id");
-- Create index "ix_reminders_time" to table: "reminders"
CREATE INDEX "ix_reminders_time" ON "reminders" ("time");
-- Create index "ix_reminders_user_id" to table: "reminders"
CREATE INDEX "ix_reminders_user_id" ON "reminders" ("user_id");
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ADD COLUMN "reminder_id" uuid NULL, ADD CONSTRAINT "scheduled_tasks_reminder_id_fkey" FOREIGN KEY ("reminder_id") REFERENCES "reminders" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
