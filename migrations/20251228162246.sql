-- Modify "fireboard_boards" table
ALTER TABLE "fireboard_boards" ADD COLUMN "send_notifications" boolean NOT NULL DEFAULT true;
