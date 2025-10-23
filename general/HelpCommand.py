from discord import Embed, Color
from discord.ext import commands
from discord.ext.commands import Bot, Cog, HelpCommand
from typing import Optional

class BetterHelpCommand(HelpCommand):
    """
    A customized help command with enhanced features.
    
    Provides detailed help messages for commands, groups and categories.

    Formatted using Discord embeds for better readability.

    Example
    ----------
    >>> # Assuming `bot` is your instance of commands.Bot
    >>> bot.help_command = BetterHelpCommand()
    >>>
    >>> # To use it in other cogs:
    >>> from configs.Bot._customHelpCommand import BetterHelpCommand
    >>>
    >>> class MyCog(commands.Cog):
    >>>     def __init__(self, bot):
    >>>         self.bot = bot
    >>>         self.bot.help_command = BetterHelpCommand()
    >>> # ... rest of your code

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


    # Get all command signature
    def get_command_signature(self, command):
        return '%s%s %s' % (self.context.clean_prefix, command.qualified_name, command.signature)


    # Send Application help message
    async def send_bot_help(self, mapping):
        embed = Embed(title="", color=Color.pink())
        embed.set_author(name="Help Menu", icon_url=self.context.bot.user.display_avatar.url if self.context.bot.user.display_avatar else None)
        visibleCommandsCount = 0

        for cog, commands in mapping.items():
            filtered = await self.filter_commands(commands, sort=True)
                
            # Collect command names rather than full signatures
            if command_names := [c.qualified_name for c in filtered]:
                cog_name = getattr(cog, "qualified_name", "No Category")
                embed.add_field(name=cog_name, value=" ".join(f"`{self.context.clean_prefix}{name}`" for name in command_names), inline=False)
                visibleCommandsCount += len(command_names)

        embed.description = f"We have **{len(mapping)}** categories and **{visibleCommandsCount}** command(s) to explore.\n\n Use `{self.context.clean_prefix}help [command]` for more info on a command.\nYou can also use `{self.context.clean_prefix}help [category]` for more info on a category."
        channel = self.get_destination()
        await channel.send(embed=embed)


    # Command help message
    async def send_command_help(self, command):
        embed = Embed(title="" , color=Color.pink())
        embed.set_author(name=f"Command {command}", icon_url=self.context.bot.user.display_avatar.url)

        if command.help:
            embed.description = command.help
            embed.add_field(name="Usage", value=f"`{self.get_command_signature(command)}`", inline=False)

        if alias := command.aliases:
            embed.add_field(name="Aliases", value=", ".join(alias), inline=False)

        channel = self.get_destination()
        await channel.send(embed=embed)


    # Group help message
    async def send_group_help(self, group):
        author = f"Group {group}"
        embed = Embed(title="", description=group.help, color=Color.pink())
        embed.set_author(name=author, icon_url=self.context.bot.user.display_avatar.url)

        if filtered_commands := await self.filter_commands(group.commands):
            for command in filtered_commands:
                embed.add_field(name=f"{self.context.clean_prefix}{command.qualified_name}", value=command.help or "No help found...", inline=False)
                embed.add_field(name="Usage", value=f"`{self.get_command_signature(command)}`" or "No help found...", inline=False)

        embed.add_field(name="", value="\u202a")    # Invisible field for spacing
        embed.set_footer(text=f"Looking for help on a specific command? Use {self.context.clean_prefix}help [command] for more that.")
        await self.get_destination().send(embed=embed)


    # Category help message
    async def send_cog_help(self, cog):
        title = cog.qualified_name or "No"
        embed = Embed(title="", description=cog.description, color=Color.pink())
        embed.set_author(name=f'{title} Category', icon_url=self.context.bot.user.display_avatar.url)

        if filtered_commands := await self.filter_commands(cog.get_commands()):
            for command in filtered_commands:
                embed.add_field(name=f"{self.context.clean_prefix}{command.qualified_name}", value=command.help or "No help found...", inline=False)

        embed.add_field(name="", value="\u202a")    # Invisible field for spacing
        embed.description = f"There are **{len(filtered_commands)}** command(s) in this category."
        embed.set_footer(text=f"Looking for help on a specific command? Use {self.context.clean_prefix}help [command] for that.")
        await self.get_destination().send(embed=embed)


    # Error message
    async def send_error_message(self, error):
        embed = Embed(title="Error", description=f"<a:crossred:1356353067024515266> {error}", color=Color.red())
        await self.get_destination().send(embed=embed)


class HelpCommand(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        # We have to remove the default help command first to avoid conflicts.
        # Then we can re-add our custom help command with the same functionality. plus hybrid support.
        self.bot.remove_command("help")


    # Same as default help command, but with hybrid command support
    @commands.hybrid_command(name="help")
    async def help(self, ctx, command_or_group: Optional[str]):
        """
        Feeling lost? No worries, help is on the way!

        Parameters
        ----------
        command_or_group : `Optional[str]`
            The command or group to get help for.

        Returns
        ----------
        None

        """
        if ctx.interaction:
            embed = Embed(title="", description="Here's some help coming your way...", color=ctx.author.color)
            await ctx.send(embed=embed, ephemeral=True)

        entity = command_or_group and (command_or_group,) or ()
        await ctx.send_help(*entity)


async def setup(bot: Bot):
    await bot.add_cog(HelpCommand(bot))
    bot.help_command = BetterHelpCommand()

