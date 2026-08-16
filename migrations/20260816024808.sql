-- Add value to enum type: "automodcriteriatype"
ALTER TYPE "automodcriteriatype" ADD VALUE 'NSFW_LINK';
-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" ALTER COLUMN "order" DROP DEFAULT;
