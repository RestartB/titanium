-- Create "available_webhooks" table
CREATE TABLE "available_webhooks" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "channel_id" bigint NOT NULL,
  "webhook_url" character varying NOT NULL,
  PRIMARY KEY ("id")
);
-- Create "guild_settings" table
CREATE TABLE "guild_settings" (
  "guild_id" bigserial NOT NULL,
  "loading_reaction" boolean NOT NULL,
  "reply_ping" boolean NOT NULL,
  "moderation_enabled" boolean NOT NULL,
  "automod_enabled" boolean NOT NULL,
  "bouncer_enabled" boolean NOT NULL,
  "logging_enabled" boolean NOT NULL,
  "fireboard_enabled" boolean NOT NULL,
  "server_counters_enabled" boolean NOT NULL,
  PRIMARY KEY ("guild_id")
);
-- Create "guild_prefixes" table
CREATE TABLE "guild_prefixes" (
  "guild_id" bigserial NOT NULL,
  "prefixes" character varying(5)[] NOT NULL DEFAULT ARRAY['t!'::character varying],
  PRIMARY KEY ("guild_id")
);
-- Create "guild_limits" table
CREATE TABLE "guild_limits" (
  "id" bigserial NOT NULL,
  "bad_word_rules" integer NOT NULL,
  "bad_word_list_size" integer NOT NULL,
  "message_spam_rules" integer NOT NULL,
  "mention_spam_rules" integer NOT NULL,
  "word_spam_rules" integer NOT NULL,
  "new_line_spam_rules" integer NOT NULL,
  "link_spam_rules" integer NOT NULL,
  "attachment_spam_rules" integer NOT NULL,
  "emoji_spam_rules" integer NOT NULL,
  PRIMARY KEY ("id")
);
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
  "rule_type" character varying(32) NOT NULL,
  "antispam_type" character varying(32) NULL,
  "rule_name" character varying(100) NULL,
  "words" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL,
  "case_sensitive" boolean NOT NULL,
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
  "rule_type" character varying(32) NOT NULL,
  "action_type" character varying(32) NOT NULL,
  "duration" bigint NULL,
  "reason" character varying(512) NULL,
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
  "enabled" boolean NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "bouncer_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_bouncer_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "bouncer_actions" table
CREATE TABLE "bouncer_actions" (
  "id" bigserial NOT NULL,
  "rule_id" uuid NOT NULL,
  "action_type" character varying(32) NOT NULL,
  "duration" bigint NULL,
  "role_id" bigint NULL,
  "reason" character varying(512) NULL,
  "message_content" character varying(2000) NULL,
  "dm_user" boolean NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "bouncer_actions_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "bouncer_rules" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "bouncer_criteria" table
CREATE TABLE "bouncer_criteria" (
  "id" bigserial NOT NULL,
  "rule_id" uuid NOT NULL,
  "criteria_type" character varying(32) NOT NULL,
  "account_age" bigint NULL,
  "words" character varying(100)[] NOT NULL DEFAULT ARRAY[]::character varying[],
  "match_whole_word" boolean NOT NULL,
  "case_sensitive" boolean NOT NULL,
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
  "reaction" character varying NOT NULL,
  "threshold" integer NOT NULL,
  "ignore_bots" boolean NOT NULL,
  "ignore_self_reactions" boolean NOT NULL,
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
  "played" integer NOT NULL,
  "win" integer NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "game_stats_game_id_fkey" FOREIGN KEY ("game_id") REFERENCES "games" ("id") ON UPDATE NO ACTION ON DELETE NO ACTION
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
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_logging_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_moderation_settings" table
CREATE TABLE "guild_moderation_settings" (
  "guild_id" bigint NOT NULL,
  "delete_confirmation" boolean NOT NULL,
  "dm_users" boolean NOT NULL,
  "immune_roles" integer[] NOT NULL DEFAULT ARRAY[]::bigint[],
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_moderation_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "guild_server_counter_settings" table
CREATE TABLE "guild_server_counter_settings" (
  "guild_id" bigint NOT NULL,
  PRIMARY KEY ("guild_id"),
  CONSTRAINT "guild_server_counter_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "mod_cases" table
CREATE TABLE "mod_cases" (
  "id" character varying(8) NOT NULL,
  "type" character varying(32) NOT NULL,
  "guild_id" bigint NOT NULL,
  "user_id" bigint NOT NULL,
  "creator_user_id" bigint NOT NULL,
  "proof_msg_id" bigint NULL,
  "proof_channel_id" bigint NULL,
  "proof_text" character varying NULL,
  "time_created" timestamp NOT NULL,
  "time_updated" timestamp NULL,
  "time_expires" timestamp NULL,
  "description" character varying(512) NULL,
  "external" boolean NOT NULL,
  "resolved" boolean NOT NULL,
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
-- Create "server_counter_channels" table
CREATE TABLE "server_counter_channels" (
  "id" bigserial NOT NULL,
  "guild_id" bigint NOT NULL,
  "count_type" character varying(32) NOT NULL,
  "name" character varying(50) NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "server_counter_channels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_server_counter_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE NO ACTION
);
