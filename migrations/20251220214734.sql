-- Modify "guild_limits" table
ALTER TABLE "guild_limits" DROP COLUMN "bad_word_rules", DROP COLUMN "message_spam_rules", DROP COLUMN "mention_spam_rules", DROP COLUMN "word_spam_rules", DROP COLUMN "new_line_spam_rules", DROP COLUMN "link_spam_rules", DROP COLUMN "attachment_spam_rules", DROP COLUMN "emoji_spam_rules", ADD COLUMN "automod_rules" integer NOT NULL DEFAULT 50;
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ALTER COLUMN "bouncer_enabled" SET DEFAULT true, ALTER COLUMN "logging_enabled" SET DEFAULT true, ALTER COLUMN "fireboard_enabled" SET DEFAULT true, ALTER COLUMN "server_counters_enabled" SET DEFAULT true;
