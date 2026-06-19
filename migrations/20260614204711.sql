-- Add value to enum type: "eventtype"
ALTER TYPE "eventtype" ADD VALUE 'POLL_END';
-- Rename a column from "answers" to "choices"
ALTER TABLE "anonymous_polls" RENAME COLUMN "answers" TO "choices";
-- Modify "anonymous_polls" table
ALTER TABLE "anonymous_polls" ADD COLUMN "message_id" bigint NOT NULL;
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ADD COLUMN "poll_id" uuid NULL, ADD CONSTRAINT "scheduled_tasks_poll_id_fkey" FOREIGN KEY ("poll_id") REFERENCES "anonymous_polls" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
