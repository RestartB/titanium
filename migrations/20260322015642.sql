-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks"
  ALTER COLUMN "id" DROP DEFAULT,
  ALTER COLUMN "id" TYPE uuid
  USING lpad(to_hex("id"), 32, '0')::uuid;

-- Drop sequence used by old bigserial
DROP SEQUENCE IF EXISTS "scheduled_tasks_id_seq";