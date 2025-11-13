-- Modify "automod_actions" table
ALTER TABLE "automod_actions" ADD COLUMN "role_id" bigint NULL;
-- Create index "ix_scheduled_tasks_time_scheduled" to table: "scheduled_tasks"
CREATE INDEX "ix_scheduled_tasks_time_scheduled" ON "scheduled_tasks" ("time_scheduled");
