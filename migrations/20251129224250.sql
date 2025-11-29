-- Drop the foreign key constraint
ALTER TABLE "fireboard_messages" DROP CONSTRAINT "fireboard_messages_fireboard_id_fkey";

-- Convert fireboard_id to text
ALTER TABLE "fireboard_messages" ALTER COLUMN "fireboard_id" TYPE text USING "fireboard_id"::text;

-- Convert id to text in the boards table
ALTER TABLE "fireboard_boards" ALTER COLUMN "id" TYPE text USING "id"::text;

-- Drop the old default
ALTER TABLE "fireboard_boards" ALTER COLUMN "id" DROP DEFAULT;

-- Drop the old sequence
DROP SEQUENCE IF EXISTS "fireboard_boards_id_seq";

-- Create a temporary mapping table to store old ID to new UUID mappings
CREATE TEMP TABLE fireboard_id_mapping AS
SELECT "id" AS old_id, gen_random_uuid()::text AS new_id
FROM "fireboard_boards";

-- Update boards with new UUIDs
UPDATE "fireboard_boards" fb
SET "id" = fim.new_id
FROM fireboard_id_mapping fim
WHERE fb."id" = fim.old_id;

-- Update messages with new UUIDs using the mapping
UPDATE "fireboard_messages" fm
SET "fireboard_id" = fim.new_id
FROM fireboard_id_mapping fim
WHERE fm."fireboard_id" = fim.old_id;

-- Convert both to UUID type
ALTER TABLE "fireboard_boards" ALTER COLUMN "id" TYPE uuid USING "id"::uuid;
ALTER TABLE "fireboard_messages" ALTER COLUMN "fireboard_id" TYPE uuid USING "fireboard_id"::uuid;

-- Set new default for id
ALTER TABLE "fireboard_boards" ALTER COLUMN "id" SET DEFAULT gen_random_uuid();

-- Recreate the foreign key constraint
ALTER TABLE "fireboard_messages" 
ADD CONSTRAINT "fireboard_messages_fireboard_id_fkey" 
FOREIGN KEY ("fireboard_id") REFERENCES "fireboard_boards"("id") ON DELETE CASCADE;