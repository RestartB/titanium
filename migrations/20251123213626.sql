-- Create enum type "leaderboardcalctype"
CREATE TYPE "leaderboardcalctype" AS ENUM ('FIXED', 'RANDOM', 'LENGTH');
-- Create enum type "automodantispamtype"
CREATE TYPE "automodantispamtype" AS ENUM ('MESSAGE', 'MENTION', 'WORD', 'NEWLINE', 'LINK', 'ATTACHMENT', 'EMOJI');
-- Create enum type "automodactiontype"
CREATE TYPE "automodactiontype" AS ENUM ('WARN', 'MUTE', 'KICK', 'BAN', 'DELETE', 'ADD_ROLE', 'REMOVE_ROLE', 'TOGGLE_ROLE');
-- Create enum type "bouncercriteriatype"
CREATE TYPE "bouncercriteriatype" AS ENUM ('USERNAME', 'TAG', 'AGE', 'AVATAR');
-- Create enum type "bounceractiontype"
CREATE TYPE "bounceractiontype" AS ENUM ('WARN', 'MUTE', 'KICK', 'BAN', 'RESET_NICK', 'ADD_ROLE', 'REMOVE_ROLE', 'TOGGLE_ROLE');
-- Create enum type "servercountertype"
CREATE TYPE "servercountertype" AS ENUM ('TOTAL_MEMBERS', 'USERS', 'BOTS', 'ONLINE_MEMBERS', 'MEMBERS_STATUS_ONLINE', 'MEMBERS_STATUS_IDLE', 'MEMBERS_STATUS_DND', 'MEMBERS_ACTIVITY', 'MEMBERS_CUSTOM_STATUS', 'OFFLINE_MEMBERS', 'CHANNELS', 'ACTIVITY');
-- Create "error_logs" table
CREATE TABLE "error_logs" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "module" character varying(100) NOT NULL,
  "error" character varying(512) NOT NULL,
  "details" character varying(1024) NULL,
  "time_occurred" timestamp NOT NULL DEFAULT now(),
  PRIMARY KEY ("id")
);
-- Create "guild_limits" table
CREATE TABLE "guild_limits" (
  "id" bigserial NOT NULL,
  "bad_word_rules" integer NOT NULL DEFAULT 10,
  "bad_word_list_size" integer NOT NULL DEFAULT 1500,
  "message_spam_rules" integer NOT NULL DEFAULT 5,
  "mention_spam_rules" integer NOT NULL DEFAULT 5,
  "word_spam_rules" integer NOT NULL DEFAULT 5,
  "new_line_spam_rules" integer NOT NULL DEFAULT 5,
  "link_spam_rules" integer NOT NULL DEFAULT 5,
  "attachment_spam_rules" integer NOT NULL DEFAULT 5,
  "emoji_spam_rules" integer NOT NULL DEFAULT 5,
  "bouncer_rules" integer NOT NULL DEFAULT 10,
  "fireboards" integer NOT NULL DEFAULT 10,
  "server_counters" integer NOT NULL DEFAULT 20,
  PRIMARY KEY ("id")
);
-- Create "guild_settings" table
CREATE TABLE "guild_settings" (
  "guild_id" bigserial NOT NULL,
  "loading_reaction" boolean NOT NULL DEFAULT true,
  "dashboard_managers" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  "case_managers" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  "moderation_enabled" boolean NOT NULL DEFAULT true,
  "automod_enabled" boolean NOT NULL DEFAULT true,
  "bouncer_enabled" boolean NOT NULL DEFAULT false,
  "logging_enabled" boolean NOT NULL DEFAULT false,
  "fireboard_enabled" boolean NOT NULL DEFAULT false,
  "server_counters_enabled" boolean NOT NULL DEFAULT false,
  "leaderboard_enabled" boolean NOT NULL DEFAULT false,
  "confessions_enabled" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("guild_id")
);
-- Create "available_webhooks" table
CREATE TABLE "available_webhooks" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "webhook_url" character varying NOT NULL,
  PRIMARY KEY ("id")
);
-- Create "leaderboard_user_stats" table
CREATE TABLE "leaderboard_user_stats" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "xp" integer NOT NULL DEFAULT 0,
  "level" integer NOT NULL DEFAULT 0,
  "daily_snapshots" integer[] NOT NULL DEFAULT ARRAY[]::integer[],
  PRIMARY KEY ("id")
);
-- Create index "ix_leaderboard_user_stats_guild_id" to table: "leaderboard_user_stats"
CREATE INDEX "ix_leaderboard_user_stats_guild_id" ON "leaderboard_user_stats" ("guild_id");
-- Create index "ix_leaderboard_user_stats_user_id" to table: "leaderboard_user_stats"
CREATE INDEX "ix_leaderboard_user_stats_user_id" ON "leaderboard_user_stats" ("user_id");
-- Create "guild_prefixes" table
CREATE TABLE "guild_prefixes" (
  "guild_id" bigserial NOT NULL,
  "prefixes" character varying(5)[] NOT NULL DEFAULT ARRAY['t!'::character varying],
  PRIMARY KEY ("guild_id")
);
-- Create enum type "automodruletype"
CREATE TYPE "automodruletype" AS ENUM ('BADWORD_DETECTION', 'SPAM_DETECTION', 'MALICIOUS_LINK', 'PHISHING_LINK');
-- Create "guild_automod_settings" table
CREATE TABLE "guild_automod_settings" (
  "guild_id" bigint NOT NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_automod_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "automod_rules" table
CREATE TABLE "automod_rules" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "rule_type" "automodruletype" NOT NULL,
  "antispam_type" "automodantispamtype" NULL,
  "rule_name" character varying(100) NULL,
  "words" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL DEFAULT false,
  "case_sensitive" boolean NOT NULL DEFAULT false,
  "threshold" integer NOT NULL,
  "duration" integer NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "automod_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "automod_actions" table
CREATE TABLE "automod_actions" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "rule_id" uuid NOT NULL,
  "rule_type" "automodruletype" NOT NULL,
  "action_type" "automodactiontype" NOT NULL,
  "duration" bigint NULL,
  "reason" character varying(512) NULL,
  "role_id" bigint NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "automod_actions_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT "automod_actions_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "automod_rules" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_bouncer_settings" table
CREATE TABLE "guild_bouncer_settings" (
  "guild_id" bigint NOT NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_bouncer_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "bouncer_rules" table
CREATE TABLE "bouncer_rules" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "rule_name" character varying(100) NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  PRIMARY KEY ("id"),
  CONSTRAINT "bouncer_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_bouncer_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "bouncer_actions" table
CREATE TABLE "bouncer_actions" (
  "id" bigserial NOT NULL,
  "rule_id" uuid NOT NULL,
  "action_type" "bounceractiontype" NOT NULL,
  "duration" bigint NULL,
  "role_id" bigint NULL,
  "reason" character varying(512) NULL,
  "message_content" character varying(2000) NULL,
  "dm_user" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "bouncer_actions_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "bouncer_rules" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "bouncer_criteria" table
CREATE TABLE "bouncer_criteria" (
  "id" bigserial NOT NULL,
  "rule_id" uuid NOT NULL,
  "criteria_type" "bouncercriteriatype" NOT NULL,
  "account_age" bigint NULL,
  "words" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL DEFAULT false,
  "case_sensitive" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id"),
  CONSTRAINT "bouncer_criteria_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "bouncer_rules" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_fireboard_settings" table
CREATE TABLE "guild_fireboard_settings" (
  "guild_id" bigint NOT NULL,
  "global_ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  "global_ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_fireboard_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "fireboard_boards" table
CREATE TABLE "fireboard_boards" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "reaction" character varying NOT NULL DEFAULT '🔥',
  "threshold" integer NOT NULL DEFAULT 5,
  "ignore_bots" boolean NOT NULL DEFAULT true,
  "ignore_self_reactions" boolean NOT NULL DEFAULT true,
  "ignored_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  "ignored_channels" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("id"),
  CONSTRAINT "fireboard_boards_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_fireboard_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "fireboard_messages" table
CREATE TABLE "fireboard_messages" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "message_id" bigint NOT NULL,
  "fireboard_message_id" bigint NOT NULL,
  "fireboard_id" bigint NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fireboard_messages_fireboard_id_fkey" FOREIGN KEY ("fireboard_id") REFERENCES "fireboard_boards" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "games" table
CREATE TABLE "games" (
  "id" serial NOT NULL,
  "name" character varying(50) NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "games_name_key" UNIQUE ("name")
);
-- Create "game_stats" table
CREATE TABLE "game_stats" (
  "id" bigserial NOT NULL,
  "user_id" bigint NOT NULL,
  "game_id" integer NOT NULL,
  "played" integer NOT NULL DEFAULT 0,
  "win" integer NOT NULL DEFAULT 0,
  PRIMARY KEY ("id"),
  CONSTRAINT "game_stats_game_id_fkey" FOREIGN KEY ("game_id") REFERENCES "games" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_confession_settings" table
CREATE TABLE "guild_confession_settings" (
  "guild_id" bigint NOT NULL,
  "confessions_in_channel" boolean NOT NULL DEFAULT true,
  "confessions_channel_id" bigint NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_confession_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_leaderboard_settings" table
CREATE TABLE "guild_leaderboard_settings" (
  "guild_id" bigint NOT NULL,
  "mode" "leaderboardcalctype" NOT NULL,
  "cooldown" integer NOT NULL DEFAULT 5,
  "base_xp" integer NOT NULL DEFAULT 10,
  "min_xp" integer NOT NULL DEFAULT 15,
  "max_xp" integer NOT NULL DEFAULT 25,
  "xp_mult" double precision NOT NULL DEFAULT 1.0,
  "levelup_notifications" boolean NOT NULL DEFAULT true,
  "notification_channel" bigint NULL,
  "web_leaderboard_enabled" boolean NOT NULL DEFAULT true,
  "web_login_required" boolean NOT NULL DEFAULT false,
  "delete_leavers" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_leaderboard_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_logging_settings" table
CREATE TABLE "guild_logging_settings" (
  "guild_id" bigint NOT NULL,
  "app_command_perm_update_id" bigint NULL,
  "dc_automod_rule_create_id" bigint NULL,
  "dc_automod_rule_update_id" bigint NULL,
  "dc_automod_rule_delete_id" bigint NULL,
  "channel_create_id" bigint NULL,
  "channel_update_id" bigint NULL,
  "channel_delete_id" bigint NULL,
  "guild_name_update_id" bigint NULL,
  "guild_afk_channel_update_id" bigint NULL,
  "guild_afk_timeout_update_id" bigint NULL,
  "guild_icon_update_id" bigint NULL,
  "guild_emoji_create_id" bigint NULL,
  "guild_emoji_delete_id" bigint NULL,
  "guild_sticker_create_id" bigint NULL,
  "guild_sticker_delete_id" bigint NULL,
  "guild_invite_create_id" bigint NULL,
  "guild_invite_delete_id" bigint NULL,
  "member_join_id" bigint NULL,
  "member_leave_id" bigint NULL,
  "member_nickname_update_id" bigint NULL,
  "member_roles_update_id" bigint NULL,
  "member_ban_id" bigint NULL,
  "member_unban_id" bigint NULL,
  "member_kick_id" bigint NULL,
  "member_timeout_id" bigint NULL,
  "member_untimeout_id" bigint NULL,
  "message_edit_id" bigint NULL,
  "message_delete_id" bigint NULL,
  "message_bulk_delete_id" bigint NULL,
  "poll_create_id" bigint NULL,
  "poll_delete_id" bigint NULL,
  "reaction_clear_id" bigint NULL,
  "reaction_clear_emoji_id" bigint NULL,
  "role_create_id" bigint NULL,
  "role_update_id" bigint NULL,
  "role_delete_id" bigint NULL,
  "scheduled_event_create_id" bigint NULL,
  "scheduled_event_update_id" bigint NULL,
  "scheduled_event_delete_id" bigint NULL,
  "soundboard_sound_create_id" bigint NULL,
  "soundboard_sound_update_id" bigint NULL,
  "soundboard_sound_delete_id" bigint NULL,
  "stage_instance_create_id" bigint NULL,
  "stage_instance_update_id" bigint NULL,
  "stage_instance_delete_id" bigint NULL,
  "thread_create_id" bigint NULL,
  "thread_update_id" bigint NULL,
  "thread_remove_id" bigint NULL,
  "thread_delete_id" bigint NULL,
  "voice_join_id" bigint NULL,
  "voice_leave_id" bigint NULL,
  "voice_move_id" bigint NULL,
  "voice_mute_id" bigint NULL,
  "voice_unmute_id" bigint NULL,
  "voice_deafen_id" bigint NULL,
  "voice_undeafen_id" bigint NULL,
  "titanium_warn_id" bigint NULL,
  "titanium_mute_id" bigint NULL,
  "titanium_unmute_id" bigint NULL,
  "titanium_kick_id" bigint NULL,
  "titanium_ban_id" bigint NULL,
  "titanium_unban_id" bigint NULL,
  "titanium_case_delete_id" bigint NULL,
  "titanium_case_comment_id" bigint NULL,
  "titanium_automod_trigger_id" bigint NULL,
  "titanium_confession_id" bigint NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_logging_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_moderation_settings" table
CREATE TABLE "guild_moderation_settings" (
  "guild_id" bigint NOT NULL,
  "delete_confirmation" boolean NOT NULL DEFAULT false,
  "dm_users" boolean NOT NULL DEFAULT true,
  "external_cases" boolean NOT NULL DEFAULT true,
  "external_case_dms" boolean NOT NULL DEFAULT false,
  "immune_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_moderation_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_server_counter_settings" table
CREATE TABLE "guild_server_counter_settings" (
  "guild_id" bigint NOT NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_server_counter_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "leaderboard_levels" table
CREATE TABLE "leaderboard_levels" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "xp" integer NOT NULL DEFAULT 0,
  "reward_roles" bigint[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("id"),
  CONSTRAINT "leaderboard_levels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_leaderboard_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "mod_cases" table
CREATE TABLE "mod_cases" (
  "id" character varying(8) NOT NULL,
  "type" character varying(32) NOT NULL,
  "guild_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "creator_user_id" bigint NOT NULL,
  "time_created" timestamp NOT NULL,
  "time_updated" timestamp NULL,
  "time_expires" timestamp NULL,
  "description" character varying(512) NULL,
  "external" boolean NOT NULL DEFAULT false,
  "resolved" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("id")
);
-- Create "mod_case_comments" table
CREATE TABLE "mod_case_comments" (
  "id" uuid NOT NULL,
  "guild_id" bigint NOT NULL,
  "case_id" character varying(8) NOT NULL,
  "user_id" bigint NOT NULL,
  "comment" character varying(512) NOT NULL,
  "time_created" timestamp NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "mod_case_comments_case_id_fkey" FOREIGN KEY ("case_id") REFERENCES "mod_cases" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "scheduled_tasks" table
CREATE TABLE "scheduled_tasks" (
  "id" bigserial NOT NULL,
  "type" character varying NOT NULL,
  "guild_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "role_id" bigint NOT NULL,
  "message_id" bigint NOT NULL,
  "case_id" character varying(8) NULL,
  "duration" bigint NULL,
  "time_scheduled" timestamp NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "scheduled_tasks_case_id_fkey" FOREIGN KEY ("case_id") REFERENCES "mod_cases" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "ix_scheduled_tasks_time_scheduled" to table: "scheduled_tasks"
CREATE INDEX "ix_scheduled_tasks_time_scheduled" ON "scheduled_tasks" ("time_scheduled");
-- Create "server_counter_channels" table
CREATE TABLE "server_counter_channels" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "count_type" "servercountertype" NOT NULL,
  "activity_name" character varying(50) NULL,
  "name" character varying(50) NOT NULL DEFAULT '{value}',
  PRIMARY KEY ("id"),
  CONSTRAINT "server_counter_channels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_server_counter_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
