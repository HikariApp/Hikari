from discord import Embed, User, Member, HTTPException, utils
from discord.ext import commands
from typing import Optional


class DisplayUserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    # Displaing an avatar of a user to everyone
    @commands.hybrid_command(aliases=["ava"])
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

        """
        
        user = user or ctx.author
        userAvatar = user.display_avatar.url
        
        embed = Embed(title="Avatar Link", url=userAvatar)
        
        embed.set_image(url=f"{userAvatar}")
        embed.set_author(name=f"{user.display_name}", icon_url=f"{userAvatar}")
        embed.set_footer(text=f'Requested by {ctx.author.display_name}', icon_url=f"{ctx.author.display_avatar.url}")
        
        await ctx.send(embed=embed)


    # Displaing the info of you or a specfied user to everyone
    # UPTATE 17-10-2025: This command has been heavily rewritten to include more info and better formatting, see Note below
    @commands.hybrid_command(aliases=["user", "whois"])
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




