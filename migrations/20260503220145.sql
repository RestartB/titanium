-- Add the new 'channels' column
ALTER TABLE "guild_logging_settings"
ADD COLUMN "channels" jsonb NOT NULL DEFAULT '{}';
-- Migrate data from the individual columns into the 'channels' jsonb column
UPDATE "guild_logging_settings" gls
SET "channels" = COALESCE(
        (
            SELECT jsonb_object_agg(regexp_replace(key, '_id$', ''), value)
            FROM jsonb_each(to_jsonb(gls))
            WHERE jsonb_typeof(value) != 'null'
                AND key != 'guild_id'
                AND key != 'channels'
        ),
        '{}'::jsonb
    );
-- Drop old columns
ALTER TABLE "guild_logging_settings" DROP COLUMN "app_command_perm_update_id",
    DROP COLUMN "dc_automod_rule_create_id",
    DROP COLUMN "dc_automod_rule_update_id",
    DROP COLUMN "dc_automod_rule_delete_id",
    DROP COLUMN "channel_create_id",
    DROP COLUMN "channel_update_id",
    DROP COLUMN "channel_delete_id",
    DROP COLUMN "guild_name_update_id",
    DROP COLUMN "guild_afk_channel_update_id",
    DROP COLUMN "guild_afk_timeout_update_id",
    DROP COLUMN "guild_icon_update_id",
    DROP COLUMN "guild_emoji_create_id",
    DROP COLUMN "guild_emoji_delete_id",
    DROP COLUMN "guild_sticker_create_id",
    DROP COLUMN "guild_sticker_delete_id",
    DROP COLUMN "guild_invite_create_id",
    DROP COLUMN "guild_invite_delete_id",
    DROP COLUMN "member_join_id",
    DROP COLUMN "member_leave_id",
    DROP COLUMN "member_nickname_update_id",
    DROP COLUMN "member_roles_update_id",
    DROP COLUMN "member_ban_id",
    DROP COLUMN "member_unban_id",
    DROP COLUMN "member_kick_id",
    DROP COLUMN "member_timeout_id",
    DROP COLUMN "member_untimeout_id",
    DROP COLUMN "message_edit_id",
    DROP COLUMN "message_delete_id",
    DROP COLUMN "message_bulk_delete_id",
    DROP COLUMN "poll_create_id",
    DROP COLUMN "poll_delete_id",
    DROP COLUMN "reaction_clear_id",
    DROP COLUMN "reaction_clear_emoji_id",
    DROP COLUMN "role_create_id",
    DROP COLUMN "role_update_id",
    DROP COLUMN "role_delete_id",
    DROP COLUMN "scheduled_event_create_id",
    DROP COLUMN "scheduled_event_update_id",
    DROP COLUMN "scheduled_event_delete_id",
    DROP COLUMN "soundboard_sound_create_id",
    DROP COLUMN "soundboard_sound_update_id",
    DROP COLUMN "soundboard_sound_delete_id",
    DROP COLUMN "stage_instance_create_id",
    DROP COLUMN "stage_instance_update_id",
    DROP COLUMN "stage_instance_delete_id",
    DROP COLUMN "thread_create_id",
    DROP COLUMN "thread_update_id",
    DROP COLUMN "thread_delete_id",
    DROP COLUMN "voice_join_id",
    DROP COLUMN "voice_leave_id",
    DROP COLUMN "voice_move_id",
    DROP COLUMN "voice_mute_id",
    DROP COLUMN "voice_unmute_id",
    DROP COLUMN "voice_deafen_id",
    DROP COLUMN "voice_undeafen_id",
    DROP COLUMN "titanium_warn_id",
    DROP COLUMN "titanium_mute_id",
    DROP COLUMN "titanium_unmute_id",
    DROP COLUMN "titanium_kick_id",
    DROP COLUMN "titanium_ban_id",
    DROP COLUMN "titanium_unban_id",
    DROP COLUMN "titanium_case_delete_id",
    DROP COLUMN "titanium_case_comment_id",
    DROP COLUMN "titanium_automod_trigger_id",
    DROP COLUMN "titanium_confession_id",
    DROP COLUMN "titanium_bouncer_trigger_id",
    DROP COLUMN "guild_features_update_id";