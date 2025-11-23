from atlas_provider_sqlalchemy.ddl import print_ddl

from . import sql

print_ddl(
    "postgresql",
    [
        sql.GuildSettings,
        sql.GuildConfessionsSettings,
        sql.GuildLimits,
        sql.GuildPrefixes,
        sql.AvailableWebhook,
        sql.GuildModerationSettings,
        sql.GuildAutomodSettings,
        sql.AutomodRule,
        sql.AutomodAction,
        sql.GuildBouncerSettings,
        sql.BouncerRule,
        sql.BouncerCriteria,
        sql.BouncerAction,
        sql.GuildLoggingSettings,
        sql.GuildFireboardSettings,
        sql.FireboardBoard,
        sql.FireboardMessage,
        sql.GuildServerCounterSettings,
        sql.ServerCounterChannel,
        sql.GuildLeaderboardSettings,
        sql.LeaderboardLevels,
        sql.LeaderboardUserStats,
        sql.ModCase,
        sql.ModCaseComment,
        sql.Game,
        sql.GameStat,
        sql.ScheduledTask,
        sql.ErrorLog,
    ],
)
