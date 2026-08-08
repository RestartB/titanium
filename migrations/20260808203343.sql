-- Migrate old role_id column to new role_ids column, when role_id has a value
UPDATE "bouncer_actions"
SET "role_ids" = CASE
  WHEN "role_id" = ANY("role_ids") THEN "role_ids"
  ELSE array_prepend("role_id", "role_ids")
END
WHERE "role_id" IS NOT NULL;

-- Modify "bouncer_actions" table
ALTER TABLE "bouncer_actions" DROP COLUMN "role_id";
