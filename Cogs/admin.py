import discord
from discord import option
from discord.ext import commands
from discord.ext.commands import CheckFailure
from discord.ui import Button, Select, View
import asyncio
import json
import os
from Cogs.utils import get_language_strings


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

        strings = await get_language_strings(ctx)

        role_dict = {"Options": [], "Errors": {"NotFound": [], "Higher": [], "NoAccess": []}}
        split_roles = roles.split(";")

        with open("Data/messages.json", "r") as message_file:
            messages = json.load(message_file)

        embed = discord.Embed(
            description=strings["RoleAssign.Initializing"].format(len(split_roles)),
            color=discord.Color.dark_green()
        )
        initial = await ctx.followup.send(embed=embed)

        select = Select(placeholder=strings["RoleSelection.Placeholder"], options=[], min_values=0)

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

                assigned_roles, removed_roles, unassigned_roles = [], [], []
                for option_ in select.values:
                    role_ = discord.utils.get(ctx.guild.roles, name=option_)

                    if role_ not in member.roles:
                        try:
                            await member.add_roles(role_)
                            assigned_roles.append(f"`{option_}`")
                        except discord.Forbidden:
                            unassigned_roles.append(f"`{option_}`")

                for option_ in unselected_options:
                    role_ = discord.utils.get(ctx.guild.roles, name=option_)

                    if role_ in member.roles:
                        try:
                            await member.remove_roles(role_)
                            removed_roles.append(f"`{option_}`")
                        except discord.Forbidden:
                            unassigned_roles.append(f"`{option_}`")

                joined_assigned = "\n".join(assigned_roles) + "\n"
                joined_removed = "\n".join(removed_roles)
                joined_unassigned = "\n".join(unassigned_roles)

                if assigned_roles or removed_roles or unassigned_roles:
                    roles_assigned_message = strings["RoleSelection.Assigned"]
                    roles_removed_message = strings["RoleSelection.Removed"]
                    roles_unassigned_message = strings["RoleSelection.Unassigned"]

                    embed_ = discord.Embed(
                        description=f"{roles_assigned_message + joined_assigned if assigned_roles else ''}"
                                    f"{roles_removed_message + joined_removed if removed_roles else ''}"
                                    f"{roles_unassigned_message + joined_unassigned if unassigned_roles else ''}",
                        color=discord.Color.dark_green() if not unassigned_roles else discord.Color.red()
                    )
                else:
                    embed_ = discord.Embed(
                        description=strings["RoleSelection.NoChanges"],
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
                    "Opts": role_dict["Options"]
                }
                with open("Data/messages.json", "w") as message_file:
                    json.dump(messages, message_file, indent=4)

        if role_dict["Errors"]["NotFound"] or role_dict["Errors"]["Higher"] or role_dict["Errors"]["NoAccess"]:
            joined_not_found = "\n".join(role_dict["Errors"]["NotFound"]) + "\n"
            joined_higher = "\n".join(role_dict["Errors"]["Higher"]) + "\n"
            joined_no_access = "\n".join(role_dict["Errors"]["NoAccess"])

            roles_not_found_error = strings["Errors.RoleSelectionNotFound"]
            roles_higher_error = strings["Errors.RoleSelectionHigher"]
            roles_no_access_error = strings["Errors.RoleSelectionNoAccess"]

            embed = discord.Embed(
                description=f"{(roles_not_found_error + joined_not_found) if role_dict['Errors']['NotFound'] else ''}"
                            f"{(roles_higher_error + joined_higher) if role_dict['Errors']['Higher'] else ''}"
                            f"{(roles_no_access_error + joined_no_access) if role_dict['Errors']['NoAccess'] else ''}",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(description="Specify the role that new users of the guild automatically get")
    @option(name="role", description="The name of the role", required=False)
    @commands.has_permissions(administrator=True)
    async def joinrole(self, ctx, role: str = None):
        strings = await get_language_strings(ctx)

        with open("Data/joinroles.json", "r") as role_file:
            roles = json.load(role_file)

        if not role:
            if str(ctx.guild.id) in roles:
                embed = discord.Embed(
                    description=strings["Admin.JoinRole"].format(roles[str(ctx.guild.id)]),
                    color=discord.Color.dark_gold()
                )
                await ctx.respond(embed=embed, ephemeral=True)
            else:
                embed = discord.Embed(
                    description=strings["Admin.JoinRoleNone"],
                    color=discord.Color.dark_gold()
                )
                await ctx.respond(embed=embed, ephemeral=True)
            return

        if discord.utils.get(ctx.guild.roles, name=role) is None:
            embed = discord.Embed(
                description=strings["Errors.JoinRoleNotFound"].format(role),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        elif discord.utils.get(ctx.guild.roles, name=role) >= \
                discord.utils.get(ctx.guild.roles, name=ctx.guild.me.top_role.name):
            embed = discord.Embed(
                description=strings["Errors.JoinRoleHigher"].format(role),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        elif not discord.utils.get(ctx.guild.roles, name=role).is_assignable():
            embed = discord.Embed(
                description=strings["Errors.JoinRoleNoAccess"].format(role),
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        roles[ctx.guild.id] = role

        with open("Data/joinroles.json", "w") as role_file:
            json.dump(roles, role_file, indent=4)

        embed = discord.Embed(
            description=strings["Admin.JoinRoleSuccess"].format(role),
            color=discord.Color.dark_green()
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Deletes a set amount of messages")
    @option(name="amount", description="The amount of messages to delete", required=True)
    @commands.has_permissions(administrator=True)
    async def msgdel(self, ctx, amount: int):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        amount = min(max(amount, 0), 100)

        embed = discord.Embed(
            description=strings["Admin.MessageDel"].format(amount),
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=strings["Admin.DeleteToCancel"])
        failsafe = await ctx.followup.send(embed=embed)
        await asyncio.sleep(10)
        await failsafe.delete()
        await ctx.channel.purge(limit=amount)

    @commands.slash_command(description="Resets the economy of the guild")
    @commands.has_permissions(administrator=True)
    async def reset_economy(self, ctx):
        await ctx.defer()

        strings = await get_language_strings(ctx)

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
                description=strings["Admin.EconomyResetSuccess"].format(ctx.guild.name),
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        async def no_button_callback(interaction: discord.Interaction):
            embed_ = discord.Embed(
                description=strings["Admin.EconomyResetCancel"].format(ctx.guild.name),
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        yes_button.callback, no_button.callback = yes_button_callback, no_button_callback
        view = View(timeout=None)
        view.add_item(yes_button), view.add_item(no_button)

        embed = discord.Embed(
            description=strings["Admin.EconomyReset"].format(ctx.guild.name),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed, view=view)

    @commands.slash_command(description="Change the guild specific settings")
    @option(name="language", description="The name of the language file, without the '.json' suffix", required=False)
    @commands.has_permissions(administrator=True)
    async def settings(self, ctx, language: str = None):
        strings = await get_language_strings(ctx)

        with open("Data/settings.json", "r") as settings_file:
            settings = json.load(settings_file)

        if not language:
            available_languages = [lang.split(".")[0] for lang in os.listdir("Locales") if lang.split(".")[1] == "json"]
            joined_available_languages = "\n".join(available_languages)

            embed = discord.Embed(
                description=strings["Settings.Desc"].format(settings[str(ctx.guild.id)], joined_available_languages),
                color=discord.Color.dark_gold()
            )
            try:
                embed.set_author(name=strings["Settings.Title"], icon_url=ctx.guild.icon.url)
            except AttributeError:
                embed.set_author(name=strings["Settings.Title"])
            await ctx.response.send_message(embed=embed)
            return
        elif not os.path.exists(f"Locales/{language}.json"):
            embed = discord.Embed(
                description=strings["Errors.LanguageFileNotFound"].format(language),
                color=discord.Color.red()
            )
            await ctx.response.send_message(embed=embed)
            return

        settings[ctx.guild.id] = language

        with open("Data/settings.json", "w") as settings_file:
            json.dump(settings, settings_file, indent=4)

        embed = discord.Embed(
            description=strings["Settings.Language"].format(ctx.guild.name, language),
            color=discord.Color.dark_green()
        )
        await ctx.response.send_message(embed=embed)

    @roleassign.error
    @joinrole.error
    @msgdel.error
    @reset_economy.error
    @settings.error
    async def reset_economy_error(self, ctx, error):
        if isinstance(error, CheckFailure):
            strings = await get_language_strings(ctx)

            embed = discord.Embed(
                description=strings["Errors.AdminOnly"],
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return


def setup(bot):
    bot.add_cog(Admin(bot))
