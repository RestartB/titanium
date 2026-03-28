-- Modify "guild_automod_settings" table
ALTER TABLE "guild_automod_settings" DROP CONSTRAINT "guild_automod_settings_guild_id_fkey", ADD CONSTRAINT "guild_automod_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "automod_rules" table
ALTER TABLE "automod_rules" DROP CONSTRAINT "automod_rules_guild_id_fkey", ADD CONSTRAINT "automod_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "automod_actions" table
ALTER TABLE "automod_actions" DROP CONSTRAINT "automod_actions_guild_id_fkey", DROP CONSTRAINT "automod_actions_rule_id_fkey", ADD CONSTRAINT "automod_actions_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_automod_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE, ADD CONSTRAINT "automod_actions_rule_id_fkey" FOREIGN KEY ("rule_id") REFERENCES "automod_rules" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_bouncer_settings" table
ALTER TABLE "guild_bouncer_settings" DROP CONSTRAINT "guild_bouncer_settings_guild_id_fkey", ADD CONSTRAINT "guild_bouncer_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "bouncer_rules" table
ALTER TABLE "bouncer_rules" DROP CONSTRAINT "bouncer_rules_guild_id_fkey", ADD CONSTRAINT "bouncer_rules_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_bouncer_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_fireboard_settings" table
ALTER TABLE "guild_fireboard_settings" DROP CONSTRAINT "guild_fireboard_settings_guild_id_fkey", ADD CONSTRAINT "guild_fireboard_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "fireboard_boards" table
ALTER TABLE "fireboard_boards" DROP CONSTRAINT "fireboard_boards_guild_id_fkey", ADD CONSTRAINT "fireboard_boards_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_fireboard_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "fireboard_messages" table
ALTER TABLE "fireboard_messages" DROP CONSTRAINT "fireboard_messages_fireboard_id_fkey", ADD CONSTRAINT "fireboard_messages_fireboard_id_fkey" FOREIGN KEY ("fireboard_id") REFERENCES "fireboard_boards" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_confession_settings" table
ALTER TABLE "guild_confession_settings" DROP CONSTRAINT "guild_confession_settings_guild_id_fkey", ADD CONSTRAINT "guild_confession_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_leaderboard_settings" table
ALTER TABLE "guild_leaderboard_settings" DROP CONSTRAINT "guild_leaderboard_settings_guild_id_fkey", ADD CONSTRAINT "guild_leaderboard_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_logging_settings" table
ALTER TABLE "guild_logging_settings" DROP CONSTRAINT "guild_logging_settings_guild_id_fkey", ADD CONSTRAINT "guild_logging_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_moderation_settings" table
ALTER TABLE "guild_moderation_settings" DROP CONSTRAINT "guild_moderation_settings_guild_id_fkey", ADD CONSTRAINT "guild_moderation_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "guild_server_counter_settings" table
ALTER TABLE "guild_server_counter_settings" DROP CONSTRAINT "guild_server_counter_settings_guild_id_fkey", ADD CONSTRAINT "guild_server_counter_settings_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "leaderboard_levels" table
ALTER TABLE "leaderboard_levels" DROP CONSTRAINT "leaderboard_levels_guild_id_fkey", ADD CONSTRAINT "leaderboard_levels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_leaderboard_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "mod_case_comments" table
ALTER TABLE "mod_case_comments" DROP CONSTRAINT "mod_case_comments_case_id_fkey", ADD CONSTRAINT "mod_case_comments_case_id_fkey" FOREIGN KEY ("case_id") REFERENCES "mod_cases" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "scheduled_tasks" table
ALTER TABLE "scheduled_tasks" DROP CONSTRAINT "scheduled_tasks_case_id_fkey", ADD CONSTRAINT "scheduled_tasks_case_id_fkey" FOREIGN KEY ("case_id") REFERENCES "mod_cases" ("id") ON UPDATE NO ACTION ON DELETE CASCADE;
-- Modify "server_counter_channels" table
ALTER TABLE "server_counter_channels" DROP CONSTRAINT "server_counter_channels_guild_id_fkey", ADD CONSTRAINT "server_counter_channels_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "guild_server_counter_settings" ("guild_id") ON UPDATE NO ACTION ON DELETE CASCADE;
