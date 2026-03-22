-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ALTER COLUMN "id" DROP DEFAULT, ALTER COLUMN "id" TYPE uuid;
-- Drop sequence used by serial column "id"
DROP SEQUENCE IF EXISTS "scheduled_tasks_id_seq";
