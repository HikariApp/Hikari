from discord import app_commands, Embed, Interaction, Activity, ActivityType, CustomActivity, Status
from discord.ext.commands import Bot, Cog
from typing import Optional
from errorhandling._errorHandling import *

class ChangeStatus(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    change = app_commands.Group(name="change", description="Change the status of the application")

    # Function to retrieve the desired activity
    async def get_type(self, type: str, name: str | None, url: str | None):        
        if type == "custom":
            return CustomActivity(name=name)
        
        
        if type is not None and type != "custom":
            return Activity(
                type=ActivityType.__getattribute__(ActivityType, type),
                name=name,
                url=url
                )
        """
        TODO: Pending to heavily rewrite

        state="In game",
        details="Playing some stuffs",
        platform="Windows 11 x64",
        timestamps={
            "start": None,
            "stop": None
                    },
        assets={
            "large_image": None,
            "large_text": None,
            "small_image": None,
            "small_text": None,
                },
        buttons=[
        ],
        emoji=None
        """

        return None    # The status has been ignored, or the user didn't select any valid option from the list.


    # Changing the status of the bot
    @change.command(name="status", description="Changing the bot status (Permitted to team admins only)")
    @app_commands.describe(status="Status of the bot")
    @app_commands.rename(activity_type="type")
    @app_commands.rename(activity_name="name")
    @app_commands.choices(status=[
        app_commands.Choice(name="Idle", value="idle"),
        app_commands.Choice(name="Invisible", value="invisible"),
        app_commands.Choice(name="Do not disturb", value="dnd"),
        app_commands.Choice(name="Online", value="online")
        ])
    @app_commands.choices(activity_type=[
        app_commands.Choice(name="Playing", value="playing"),
        app_commands.Choice(name="Streaming", value="streaming"),
        app_commands.Choice(name="Listening to", value="listening"),
        app_commands.Choice(name="Watching", value="watching"),
        app_commands.Choice(name="Custom", value="custom"),
        app_commands.Choice(name="Competing In", value="competing")
        ])
    async def change_status(self, interaction: Interaction, status: app_commands.Choice[str], activity_type: Optional[app_commands.Choice[str]] = None, activity_name: Optional[str] = None, url: Optional[str] = None):
        """
        Changing the bot status (Permitted to team admins only)

        Parameters
        ----------
        status : app_commands.Choice[str]
            Status of the bot

        activity_type : Optional[app_commands.Choice[str]]
            The type you would like to display. Choose '(Ignore)' if you want to leave it blank.

        activity_name : Optional[app_commands.Choice[str]]
            The text you would like the bot to display on bio

        url : Optional[str]
            The URL you want to redirect (For streaming only)

        Returns
        -------
        None

        """

        embed = Embed(title="", color=interaction.user.color)
        if not await self.bot.is_owner(interaction.user):
            return await interaction.response.send_message(NotBotOwnerError())
        
        embed.add_field(name="", value=f"Changing status...", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True, delete_after=0)

        # Set the status to the selected option.
        status = Status.__getattribute__(Status, status.value)

        selected_activity = await self.get_type(type=activity_type.value if activity_type else None, name=activity_name, url=url) if activity_type else None
        await self.bot.change_presence(status=status, activity=selected_activity)


async def setup(bot: Bot):
    await bot.add_cog(ChangeStatus(bot))
