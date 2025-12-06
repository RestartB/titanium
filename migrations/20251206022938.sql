-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" ALTER COLUMN "guild_id" DROP NOT NULL, ALTER COLUMN "user_id" DROP NOT NULL, ALTER COLUMN "channel_id" DROP NOT NULL, ALTER COLUMN "role_id" DROP NOT NULL, ALTER COLUMN "message_id" DROP NOT NULL;
