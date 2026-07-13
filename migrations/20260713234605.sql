-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ADD COLUMN "retry_amount" integer NOT NULL DEFAULT 0;
