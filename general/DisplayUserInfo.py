from discord import app_commands, Embed, Interaction, User, Member, SelectOption, HTTPException, utils
from discord.ui import View, Select
from discord.ext import commands
from typing import Optional

# Helper function to create an avatar embed
async def createAvatarEmbed(user: User, avatar_url: str) -> Embed:
    """
    This function is a [coroutine](https://docs.python.org/3/library/asyncio-task.html#coroutine).

    Creates and returns an embed containing the user's avatar.

    Parameters
    ----------
    user : `discord.User`
        The user whose avatar is to be displayed.

    avatar_url : `str`
        The URL of the avatar image.

    Returns
    ----------
    embed : `discord.Embed`
        An embed object containing the user's avatar.
    
    """

    embed = Embed()
    embed.set_image(url=avatar_url)
    embed.set_author(name=f"{user.display_name}", icon_url=avatar_url)
    return embed

# Dropdown menu for selecting avatar type
class AvatarSelectForGuild(Select):
    def __init__(self, user):
        options = [
            SelectOption(label="Global Avatar", value="global"),
            SelectOption(label="Server Avatar", value="server"),
        ]
        super().__init__(placeholder="Choose an avatar type...", options=options)
        self.user = user

    async def callback(self, interaction: Interaction):
        embed = None

        if self.values[0] == "global":
            avatar_url = self.user.display_avatar.url
            embed = await createAvatarEmbed(self.user, avatar_url)
            embed.title = "Global Avatar"

        else:
            member = interaction.guild.get_member(self.user.id)
            avatar_url = member.display_avatar.url if member else self.user.display_avatar.url
            embed = await createAvatarEmbed(self.user, avatar_url)
            embed.title = "Server Avatar"
        
        embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url)
        await interaction.response.edit_message(embed=embed)

class DisplayUserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Displaying the avatar of you or a specfied user to everyone
    # UPTATE 18-10-2025: This command has been heavily rewritten to include more info and better formatting, see Note below
    @commands.hybrid_command(aliases=["ava"])
    @app_commands.allowed_installs(users=True, guilds=True)
    async def avatar(self, ctx: commands.Context, user: Optional[User] = None):
        """
        Displays your avatar or someone else's avatar to everyone.

        Parameters
        ----------
        ctx : `commands.Context`
            The context in which the command was invoked.

        user : `Optional[discord.User]`
            The user to get the avatar for. Leave this blank if you want to get your own avatar.

        Returns
        ----------
        None

        Note
        ----------
        This command has been heavily rewritten to provide a more comprehensive overview of the user's information.
        - It now includes a dropdown menu to select between the user's global avatar and server-specific avatar (if applicable).
        - The embed now displays the avatar in a larger format for better visibility.
        - The formatting of the embed has been improved for clarity.

        """
        
        user = user or ctx.author
        embed = await createAvatarEmbed(user, user.display_avatar.url)
        embed.title = "Global Avatar"
        view = None
        
        if ctx.guild is not None:    # If not in a guild just show the global avatar to prevent errors
            select = AvatarSelectForGuild(user)
            view = View()
            view.add_item(select)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
        await ctx.send(embed=embed, view=view or None)


    # Displaing the info of you or a specfied user to everyone
    # UPTATE 17-10-2025: This command has been heavily rewritten to include more info and better formatting, see Note below
    @commands.hybrid_command(aliases=["user", "whois"])
    @app_commands.allowed_installs(users=True, guilds=True)
    async def userinfo(self, ctx: commands.Context, user: Optional[User] = None):
        """
        Displays information about yourself or another member in the server, such as ID and joined date.

        Parameters
        ----------
        ctx : `commands.Context`
            The context in which the command was invoked.

        user : `Optional[discord.User]`
            The user to get info about. Leave this blank if you want to get your own info.

        Returns
        ----------
        None

        Note
        ----------
        This command has been heavily rewritten to provide a more comprehensive overview of the user's information.

        - It now includes the user's global name (if set) and indicates if they are the server owner with a crown emoji.
        - The embed now displays the user's roles in the server (if applicable) and their accent color.
        - The formatting of dates has been improved to show both the exact date and a relative time.
        - If the user has a banner, it will be displayed in the embed.

        """

        user = user or ctx.author

        # Try to find the user as a member of the current guild
        member: Optional[Member] = None
        if ctx.guild:
            member = ctx.guild.get_member(user.id)
        
        embed = Embed()
        embed.set_author(name=f"{user.global_name if user.global_name else user.display_name} {' \U0001F451' if (member and member.id == member.guild.owner.id) else ''}", icon_url=f"{user.display_avatar.url}")
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Username:", value=f"{user.name}", inline=False)
        embed.add_field(name="ID:", value=user.id, inline=False)

        if user.discriminator != "0": # Only show discriminator if it's not "0"
            embed.add_field(name="Discriminator:", value=f"#{user.discriminator}", inline=False)

        if isinstance(user, Member):
            embed.add_field(name="Name in Guild:", value=member.display_name, inline=False)
            embed.add_field(name="Roles:", value=", ".join(role.mention for role in member.roles if role.name != "@everyone") or "No Roles", inline=False)

        embed.add_field(name="Color:", value=user.accent_color or user.color, inline=False)
        embed.add_field(name="", value="\u202a", inline=False)  # Empty field for spacing

        embed.add_field(name="Member on Discord:", value=f"**{utils.format_dt(user.created_at, style='D')} ({utils.format_dt(user.created_at, style='R')})**", inline=False)
        
        if isinstance(user, Member):
            embed.add_field(name="Member since:", value=f"**{utils.format_dt(member.joined_at, style='D')} ({utils.format_dt(member.joined_at, style='R')})**", inline=False)

        embed.add_field(name="", value="\u202a", inline=False)  # Empty field for spacing

        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url)
        embed.color = user.color

        # Generally, user.banner is None unless the user is cached, even if they have a banner.
        if user.banner is None:
            try:
                user = await self.bot.fetch_user(user.id)
                
            except HTTPException:
                pass  # Couldn’t fetch user

        if user.banner.url:    # At this point, user.banner might exist
            embed.set_image(url=user.banner.url)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(DisplayUserInfo(bot))



