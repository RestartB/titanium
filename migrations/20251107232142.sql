-- Modify "automod_rules" table
ALTER TABLE "automod_rules" ALTER COLUMN "match_whole_word" SET DEFAULT false, ALTER COLUMN "case_sensitive" SET DEFAULT false;
-- Modify "bouncer_actions" table
ALTER TABLE "bouncer_actions" ALTER COLUMN "dm_user" SET DEFAULT false;
-- Modify "bouncer_criteria" table
ALTER TABLE "bouncer_criteria" ALTER COLUMN "match_whole_word" SET DEFAULT false, ALTER COLUMN "case_sensitive" SET DEFAULT false;
-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" ALTER COLUMN "enabled" SET DEFAULT true;
-- Modify "error_logs" table
ALTER TABLE "error_logs" ALTER COLUMN "time_occurred" SET DEFAULT now();
-- Modify "fireboard_boards" table
ALTER TABLE "fireboard_boards" ALTER COLUMN "reaction" SET DEFAULT '🔥', ALTER COLUMN "threshold" SET DEFAULT 5, ALTER COLUMN "ignore_bots" SET DEFAULT true, ALTER COLUMN "ignore_self_reactions" SET DEFAULT true;
-- Modify "game_stats" table
ALTER TABLE "game_stats" ALTER COLUMN "played" SET DEFAULT 0, ALTER COLUMN "win" SET DEFAULT 0;
-- Modify "guild_limits" table
ALTER TABLE "guild_limits" ALTER COLUMN "bad_word_rules" SET DEFAULT 10, ALTER COLUMN "bad_word_list_size" SET DEFAULT 1500, ALTER COLUMN "message_spam_rules" SET DEFAULT 5, ALTER COLUMN "mention_spam_rules" SET DEFAULT 5, ALTER COLUMN "word_spam_rules" SET DEFAULT 5, ALTER COLUMN "new_line_spam_rules" SET DEFAULT 5, ALTER COLUMN "link_spam_rules" SET DEFAULT 5, ALTER COLUMN "attachment_spam_rules" SET DEFAULT 5, ALTER COLUMN "emoji_spam_rules" SET DEFAULT 5, ALTER COLUMN "bouncer_rules" SET DEFAULT 10, ALTER COLUMN "fireboards" SET DEFAULT 10, ALTER COLUMN "server_counters" SET DEFAULT 20;
-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings" ALTER COLUMN "delete_confirmation" SET DEFAULT false, ALTER COLUMN "dm_users" SET DEFAULT true, ALTER COLUMN "immune_roles" TYPE bigint[];
-- Modify "guild_settings" table
ALTER TABLE "guild_settings" ALTER COLUMN "loading_reaction" SET DEFAULT true, ALTER COLUMN "moderation_enabled" SET DEFAULT true, ALTER COLUMN "automod_enabled" SET DEFAULT true, ALTER COLUMN "bouncer_enabled" SET DEFAULT false, ALTER COLUMN "logging_enabled" SET DEFAULT false, ALTER COLUMN "fireboard_enabled" SET DEFAULT false, ALTER COLUMN "server_counters_enabled" SET DEFAULT false, ALTER COLUMN "confession_enabled" SET DEFAULT false;
-- Modify "mod_cases" table
ALTER TABLE "mod_cases" ALTER COLUMN "external" SET DEFAULT false, ALTER COLUMN "resolved" SET DEFAULT false;
-- Modify "server_counter_channels" table
ALTER TABLE "server_counter_channels" ALTER COLUMN "name" SET DEFAULT '{value}';
