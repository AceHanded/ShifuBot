import discord
from discord import option
from discord.ext import commands
from discord.ext.commands import CheckFailure
from discord.ui import Button, Select, View
import asyncio
import json


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Create a message for self-assigning roles")
    @option(name="roles", description="The roles separated by semicolons (i.e. role1;role2;...)", required=True)
    @option(name="message", description="The contents of the message", required=False)
    @option(name="modify", description="The ID of the message to modify", required=False)
    @commands.has_permissions(administrator=True)
    async def roleassign(self, ctx, roles: str, message: str = "Role assignment time.", modify: str = None):
        await ctx.defer()

        role_dict = {"Options": [], "Errors": {"NotFound": [], "Higher": [], "NoAccess": []}}
        split_roles = roles.split(";")

        with open("Data/messages.json", "r") as message_file:
            messages = json.load(message_file)

        embed = discord.Embed(
            description=f"Initializing **{len(split_roles)}** roles...",
            color=discord.Color.dark_green()
        )
        initial = await ctx.followup.send(embed=embed)

        select = Select(placeholder="Waiting for role selection...", options=[], min_values=0)

        running_number = 1
        for role in split_roles:
            if discord.utils.get(ctx.guild.roles, name=role) is None:
                role_dict["Errors"]["NotFound"].append(f"`{role}`")
                continue
            elif discord.utils.get(ctx.guild.roles, name=role) >= \
                    discord.utils.get(ctx.guild.roles, name=ctx.guild.me.top_role.name):
                role_dict["Errors"]["Higher"].append(f"`{role}`")
                continue
            elif not discord.utils.get(ctx.guild.roles, name=role).is_assignable():
                role_dict["Errors"]["NoAccess"].append(f"`{role}`")
                continue

            async def role_callback(interaction: discord.Interaction):
                member = self.bot.get_guild(interaction.guild_id).get_member(interaction.user.id)

                unselected_options = [option_.label for option_ in select.options if option_.value not in select.values]

                assigned_roles, removed_roles = [], []
                for option_ in select.values:
                    role_ = discord.utils.get(ctx.guild.roles, name=option_)

                    if role_ not in member.roles:
                        await member.add_roles(role_)
                        assigned_roles.append(f"`{option_}`")

                for option_ in unselected_options:
                    role_ = discord.utils.get(ctx.guild.roles, name=option_)

                    if role_ in member.roles:
                        await member.remove_roles(role_)
                        removed_roles.append(f"`{option_}`")

                joined_assigned = "\n".join(assigned_roles) + "\n"
                joined_removed = "\n".join(removed_roles)

                if assigned_roles or removed_roles:
                    roles_assigned_message = "You have **assigned** the following roles to yourself:\n"
                    roles_removed_message = "You have **removed** the following roles from yourself:\n"

                    embed_ = discord.Embed(
                        description=f"{roles_assigned_message + joined_assigned if assigned_roles else ''}"
                                    f"{roles_removed_message + joined_removed if removed_roles else ''}",
                        color=discord.Color.dark_green()
                    )
                else:
                    embed_ = discord.Embed(
                        description=f"No changes made to roles.",
                        color=discord.Color.dark_green()
                    )
                await interaction.response.send_message(embed=embed_, ephemeral=True)

            select.callback = role_callback
            select.add_option(label=role, value=role, description=f"{running_number} - {role}")
            role_dict["Options"].append(role)
            running_number += 1

        if len(role_dict["Options"]) > 0:
            select.max_values = len(role_dict["Options"])
        else:
            select.max_values = 1

        view = View(timeout=None)
        view.add_item(select)

        await initial.delete()

        if role_dict["Options"]:
            embed = discord.Embed(
                description=f"{message}",
                color=discord.Color.dark_green()
            )
            if modify:
                message_ = await ctx.fetch_message(modify)
                await message_.edit(embed=embed, view=view)
            else:
                message_ = await ctx.send(embed=embed, view=view)

                messages[ctx.guild.id] = {
                    "MessageID": int(message_.id),
                    "ChannelID": int(ctx.channel.id),
                    "Opts": role_dict['Options']
                }
                with open("Data/messages.json", "w") as message_file:
                    json.dump(messages, message_file, indent=4)

        if role_dict["Errors"]["NotFound"] or role_dict["Errors"]["Higher"] or role_dict["Errors"]["NoAccess"]:
            joined_not_found = "\n".join(role_dict["Errors"]["NotFound"]) + "\n"
            joined_higher = "\n".join(role_dict["Errors"]["Higher"]) + "\n"
            joined_no_access = "\n".join(role_dict["Errors"]["NoAccess"])

            roles_not_found_error = "**Error:** These roles were not found:\n"
            roles_higher_error = "**Error:** These roles were higher in the hierarchy:\n"
            roles_no_access_error = "**Error:** These roles could not be accessed due to permission issues:\n"

            embed = discord.Embed(
                description=f"{(roles_not_found_error + joined_not_found) if role_dict['Errors']['NotFound'] else ''}"
                            f"{(roles_higher_error + joined_higher) if role_dict['Errors']['Higher'] else ''}"
                            f"{(roles_no_access_error + joined_no_access) if role_dict['Errors']['NoAccess'] else ''}",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @roleassign.error
    async def roleassign_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            embed = discord.Embed(
                description="**Error:** Apologies, only admins are able to execute a command this powerful.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

    @commands.slash_command(description="Specify the role that new users of the server automatically get")
    @option(name="role", description="The name of the role", required=False)
    @commands.has_permissions(administrator=True)
    async def joinrole(self, ctx, role: str = None):
        with open("Data/joinroles.json", "r") as role_file:
            roles = json.load(role_file)

        if not role:
            if str(ctx.guild.id) in roles:
                embed = discord.Embed(
                    description=f"The initial role of the server is currently: `{roles[str(ctx.guild.id)]}`",
                    color=discord.Color.dark_gold()
                )
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    description=f"No initial role has been set for the server yet.",
                    color=discord.Color.dark_gold()
                )
                await ctx.respond(embed=embed, ephemeral=True)
            return

        if discord.utils.get(ctx.guild.roles, name=role) is None:
            embed = discord.Embed(
                description=f"**Error:** Could not find the role: `{role}`",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        elif discord.utils.get(ctx.guild.roles, name=role) >= \
                discord.utils.get(ctx.guild.roles, name=ctx.guild.me.top_role.name):
            embed = discord.Embed(
                description=f"**Error:** This role is higher in the hierarchy than mine: `{role}`",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        elif not discord.utils.get(ctx.guild.roles, name=role).is_assignable():
            embed = discord.Embed(
                description=f"**Error:** I cannot access this role due to permission issues: `{role}`",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        roles[ctx.guild.id] = role

        with open("Data/joinroles.json", "w") as role_file:
            json.dump(roles, role_file, indent=4)

        embed = discord.Embed(
            description=f"Successfully changed the initial role of the server to: `{role}`",
            color=discord.Color.dark_green()
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @joinrole.error
    async def joinrole_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            embed = discord.Embed(
                description="**Error:** Apologies, only admins are able to execute a command this powerful.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

    @commands.slash_command(description="Deletes a set amount of messages", pass_context=True)
    @option("amount", description="The amount of messages to delete", required=True)
    @commands.has_permissions(administrator=True)
    async def msgdel(self, ctx, amount: int):
        await ctx.defer()

        amount = min(max(amount, 0), 100)

        embed = discord.Embed(
            description=f"Deleting **{amount}** message(s), please wait a few seconds...",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="Note: If you wish to cancel, delete this message.")
        failsafe = await ctx.followup.send(embed=embed)
        await asyncio.sleep(10)
        await failsafe.delete()
        await ctx.channel.purge(limit=amount)

    @msgdel.error
    async def msgdel_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            embed = discord.Embed(
                description="**Error:** Apologies, only admins are able to execute a command this powerful.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

    @commands.slash_command(description="Resets the economy of the server", pass_context=True)
    @commands.has_permissions(administrator=True)
    async def reset_economy(self, ctx):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        yes_button = Button(style=discord.ButtonStyle.success, label="Yes", row=1)
        no_button = Button(style=discord.ButtonStyle.danger, label="No", row=1)

        async def yes_button_callback(interaction: discord.Interaction):
            for user in users:
                user_id = int(user.split("-")[0])
                guild_id = int(user.split("-")[1])
                author_and_guild = f"{user_id}-{ctx.guild.id}"

                if guild_id == ctx.guild.id:
                    users[author_and_guild]["Wallet"] = 0
                    users[author_and_guild]["Bank"] = 100
                    users[author_and_guild]["Inventory"] = {}

                    with open("Data/economics.json", "w") as economy_file_:
                        json.dump(users, economy_file_, indent=4)

            embed_ = discord.Embed(
                description=f"The economy of **{ctx.guild.name}** has been reset.",
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        async def no_button_callback(interaction: discord.Interaction):
            embed_ = discord.Embed(
                description=f"The economy reset for **{ctx.guild.name}** has been cancelled.",
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        yes_button.callback, no_button.callback = yes_button_callback, no_button_callback
        view = View(timeout=None)
        view.add_item(yes_button), view.add_item(no_button)

        embed = discord.Embed(
            description=f"Are you sure you wish to reset the economy of **{ctx.guild.name}**?",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed, view=view)


def setup(bot):
    bot.add_cog(Admin(bot))
