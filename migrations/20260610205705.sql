-- Create "reminders" table
CREATE TABLE "reminders" (
  "id" character varying(8) NOT NULL,
  "guild_id" bigint NULL,
  "channel_id" bigint NULL,
  "user_id" bigint NOT NULL,
  "dm" boolean NOT NULL,
  "time" timestamptz NOT NULL,
  "time_created" timestamptz NOT NULL DEFAULT now(),
  "content" character varying NOT NULL,
  PRIMARY KEY ("id")
);
-- Create index "ix_reminders_user_id" to table: "reminders"
CREATE INDEX "ix_reminders_user_id" ON "reminders" ("user_id");
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ALTER COLUMN "reminder_id" TYPE character varying(8), ADD CONSTRAINT "scheduled_tasks_reminder_id_fkey" FOREIGN KEY ("reminder_id") REFERENCES "reminders" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
