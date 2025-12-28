from typing import TYPE_CHECKING

from discord.ext import commands

if TYPE_CHECKING:
    from main import TitaniumBot


def global_alias(name: str):
    def decorator(func):
        if not hasattr(func, "_global_aliases"):
            func._global_aliases = []

        func._global_aliases.append(name)
        return func

    return decorator


def add_global_aliases(cog: commands.Cog, bot: TitaniumBot):
    # disable for now
    return

    for command in cog.walk_commands():
        if isinstance(command, (commands.Group, commands.HybridGroup)):
            continue

        callback = command.callback

        if hasattr(callback, "_global_aliases"):
            aliases: list[str] = getattr(callback, "_global_aliases")

            # copy command with alias as name
            for alias in aliases:
                for existing_cmd in bot.commands:
                    if existing_cmd.name == alias:
                        bot.remove_command(alias)

                # ignore current name / parent
                kwargs = {
                    k: v
                    for k, v in command.__original_kwargs__.items()
                    if k not in ("name", "parent")
                }

                cmd_copy = commands.Command(callback, name=alias, **kwargs)
                cmd_copy.cog = cog

                bot.add_command(cmd_copy)
