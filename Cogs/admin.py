import discord
from discord.ext import commands
from discord.ext.commands import CheckFailure
from discord.ui import Button, Select, View
import asyncio
import json


class Admin(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.gui = {}
        self.views = {}

    @staticmethod
    async def resolve_gui_callback(ctx: discord.ApplicationContext, gui_element: str):
        async def yes_callback(interaction: discord.Interaction):
            with open("Data/economics.json", "r") as economy_file:
                users = json.load(economy_file)

            for user in users:
                guild_id = int(user.split("-")[1])

                if guild_id == ctx.guild.id:
                    author_and_guild = f"{user.split('-')[0]}-{guild_id}"
                    users[author_and_guild]["wallet"] = 0
                    users[author_and_guild]["bank"] = 100

            with open("Data/economics.json", "w") as economy_file:
                json.dump(users, economy_file, indent=4)

            embed = discord.Embed(
                description=f"Successfully reset the economy of **{ctx.guild.name}**.",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        async def no_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                description=f"Canceled economy reset of **{ctx.guild.name}**.",
                color=discord.Color.dark_red()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        callbacks = {
            "yes": yes_callback,
            "no": no_callback
        }
        return callbacks[gui_element]

    @commands.slash_command(description="Create a message for self-assigning roles", guild_ids=["627225744317087745"])
    @discord.option(name="roles", description="The roles separated by semicolons (i.e. role1;role2;...)", required=True)
    @discord.option(name="message", description="The contents of the message", required=False)
    @discord.option(name="modify", description="The ID of the message to modify", required=False)
    @commands.has_permissions(administrator=True)
    async def role_assign(self, ctx: discord.ApplicationContext, roles: str, message: str = "Role assignment time.",
                          modify: str = None):
        if modify and not modify.isdigit():
            embed = discord.Embed(
                description="**Error:** The parameter `modify` must contain a message ID.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        role_dict = {"opts": [], "errors": {"not_found": [], "higher": [], "no_access": []}}
        split_roles = [role.strip() for role in roles.split(";") if not role.isspace()]

        if not split_roles:
            embed = discord.Embed(
                description="**Error:** Must specify at least one role.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        # TODO : change(?)
        embed = discord.Embed(
            description=f"Initializing **{len(split_roles)}** role(s).",
            color=discord.Color.dark_green()
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

        with open("Data/messages.json", "r") as message_file:
            messages = json.load(message_file)

        select = Select(placeholder="Roles...", options=[], min_values=0)

        running_number = 1
        for role in split_roles:
            if not discord.utils.get(ctx.guild.roles, name=role):
                role_dict["errors"]["not_found"].append(f"`{role}`")
                continue
            elif discord.utils.get(ctx.guild.roles, name=role) >= \
                    discord.utils.get(ctx.guild.roles, name=ctx.guild.me.top_role.name):
                role_dict["errors"]["higher"].append(f"`{role}`")
                continue
            elif not discord.utils.get(ctx.guild.roles, name=role).is_assignable():
                role_dict["errors"]["no_access"].append(f"`{role}`")
                continue

            async def role_callback(interaction: discord.Interaction):
                member = self.bot.get_guild(interaction.guild_id).get_member(interaction.user.id)

                assigned_roles, removed_roles, unassigned_roles = [], [], []
                unselected_options = [option_.label for option_ in select.options if option_.value not in select.values]
                options = set(select.values) | set(unselected_options)

                for option in options:
                    role_ = discord.utils.get(interaction.guild.roles, name=option)

                    try:
                        if option in select.values and role_ not in member.roles:
                            await member.add_roles(role_)
                            assigned_roles.append(f"`{option}`")
                        elif option in unselected_options and role_ in member.roles:
                            await member.remove_roles(role_)
                            removed_roles.append(f"`{option}`")
                    except discord.Forbidden:
                        unassigned_roles.append(f"`{option}`")

                if assigned_roles or removed_roles or unassigned_roles:
                    joined_assigned = "\n".join(assigned_roles)
                    joined_removed = "\n".join(removed_roles)
                    joined_unassigned = "\n".join(unassigned_roles)

                    roles_assigned_message = (f"You have **assigned** the following roles to yourself:\n"
                                              f"{joined_assigned}\n")
                    roles_removed_message = (f"You have **removed** the following roles from yourself:\n"
                                             f"{joined_removed}\n")
                    roles_unassigned_message = (f"The following roles could not be accessed due to permission issues:\n"
                                                f"{joined_unassigned}\n\nPlease ensure that the bot has the "
                                                f"`Manage Roles` permission.")

                    embed_ = discord.Embed(
                        description=f"{roles_assigned_message if assigned_roles else ''}"
                                    f"{roles_removed_message if removed_roles else ''}"
                                    f"{roles_unassigned_message if unassigned_roles else ''}",
                        color=discord.Color.dark_green() if not unassigned_roles else discord.Color.red()
                    )
                else:
                    embed_ = discord.Embed(
                        description="No changes made to roles.",
                        color=discord.Color.dark_green()
                    )
                await interaction.response.send_message(embed=embed_, ephemeral=True)

            select.callback = role_callback
            select.add_option(label=role, value=role, description=f"{running_number} - {role}")
            role_dict["opts"].append(role)
            running_number += 1

        select.max_values = len(role_dict["opts"]) if len(role_dict["opts"]) > 0 else 1

        view = View(timeout=None)
        view.add_item(select)

        if role_dict["opts"]:
            embed = discord.Embed(
                description=message,
                color=discord.Color.dark_green()
            )
            if modify:
                message_ = await ctx.fetch_message(int(modify))
                await message_.edit(embed=embed, view=view)
            else:
                message_ = await ctx.send(embed=embed, view=view)

            messages[ctx.guild.id] = {
                "message_id": int(message_.id),
                "channel_id": int(ctx.channel.id),
                "opts": role_dict["opts"]
            }
            with open("Data/messages.json", "w") as message_file:
                json.dump(messages, message_file, indent=4)

        if role_dict["errors"]["not_found"] or role_dict["errors"]["higher"] or role_dict["errors"]["no_access"]:
            joined_not_found = "\n".join(role_dict["errors"]["not_found"])
            joined_higher = "\n".join(role_dict["errors"]["higher"])
            joined_no_access = "\n".join(role_dict["errors"]["no_access"])

            roles_not_found_error = f"**Error:** These roles were not found:\n{joined_not_found}\n"
            roles_higher_error = f"**Error:** These roles were higher in the hierarchy:\n{joined_higher}\n"
            roles_no_access_error = (f"**Error:** These roles could not be accessed due to permission issues:\n"
                                     f"{joined_no_access}\n\nPlease ensure that the bot has the `Manage Roles` "
                                     f"permission.")

            embed = discord.Embed(
                description=f"{roles_not_found_error if role_dict['errors']['not_found'] else ''}"
                            f"{roles_higher_error if role_dict['errors']['higher'] else ''}"
                            f"{roles_no_access_error if role_dict['errors']['no_access'] else ''}",
                color=discord.Color.red()
            )
            await ctx.followup.send(embed=embed, ephemeral=True)

    @commands.slash_command(description="Specify the role that new users of the guild automatically get")
    @discord.option(name="role", description="The name of the role", required=False)
    @commands.has_permissions(administrator=True)
    async def joinrole(self, ctx: discord.ApplicationContext, role: str = None):
        with open("Data/joinroles.json", "r") as role_file:
            roles = json.load(role_file)

        guild_id = str(ctx.guild.id)

        if not role and guild_id in roles:
            embed = discord.Embed(
                description=f"The initial role of the guild is currently: `{roles[guild_id]}`",
                color=discord.Color.dark_gold()
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return
        elif not role and guild_id not in roles:
            embed = discord.Embed(
                description="No initial role has been set for the guild yet.",
                color=discord.Color.dark_gold()
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return

        if not discord.utils.get(ctx.guild.roles, name=role):
            embed = discord.Embed(
                description=f"**Error:** Could not find the role: `{role}`",
                color=discord.Color.red()
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return
        elif discord.utils.get(ctx.guild.roles, name=role) >= \
                discord.utils.get(ctx.guild.roles, name=ctx.guild.me.top_role.name):
            embed = discord.Embed(
                description=f"**Error:** The following role is higher in the hierarchy: `{role}`",
                color=discord.Color.red()
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return
        elif not discord.utils.get(ctx.guild.roles, name=role).is_assignable():
            embed = discord.Embed(
                description=f"**Error:** The following role could not be accessed due to permission issues: `{role}`",
                color=discord.Color.red()
            )
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return

        roles[guild_id] = role

        with open("Data/joinroles.json", "w") as role_file:
            json.dump(roles, role_file, indent=4)

        embed = discord.Embed(
            description=f"Successfully changed the initial role of the guild to: `{role}`",
            color=discord.Color.dark_green()
        )
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Deletes a set amount of messages")
    @discord.option(name="amount", description="The amount of messages to delete", required=True)
    @commands.has_permissions(administrator=True)
    async def msgdel(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer()

        amount = min(max(amount, 0), 150)

        embed = discord.Embed(
            description=f"Deleting **{amount}** message(s), please wait a few seconds...",
            color=discord.Color.dark_red()
        )
        embed.set_footer(text="Note: If you wish to cancel, delete this message.")
        failsafe = await ctx.respond(embed=embed)
        await asyncio.sleep(10)
        await failsafe.delete()
        await ctx.channel.purge(limit=amount)

    @commands.slash_command(description="Resets the economy of the guild")
    @commands.has_permissions(administrator=True)
    async def reset_economy(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        embed = discord.Embed(
            description=f"Are you sure you wish to reset the economy of **{ctx.guild.name}**?",
            color=discord.Color.dark_green()
        )
        await ctx.followup.send(embed=embed, view=self.views[ctx.guild.id])

    @role_assign.error
    @joinrole.error
    @msgdel.error
    @reset_economy.error
    async def command_permission_error(self, ctx: discord.ApplicationContext, error: any):
        if isinstance(error, CheckFailure):
            embed = discord.Embed(
                description="**Error:** Only admins are able to execute this command.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @reset_economy.before_invoke
    async def ensure_dicts(self, ctx: discord.ApplicationContext):
        if ctx.guild.id not in self.gui:
            self.gui[ctx.guild.id] = {
                "yes": Button(style=discord.ButtonStyle.success, label="Yes", row=1),
                "no": Button(style=discord.ButtonStyle.danger, label="No", row=1)
            }
            self.views[ctx.guild.id] = View(timeout=None)

            for elem in self.gui[ctx.guild.id].keys():
                self.gui[ctx.guild.id][elem].callback = await self.resolve_gui_callback(ctx, elem)
                self.views[ctx.guild.id].add_item(self.gui[ctx.guild.id][elem])


def setup(bot):
    bot.add_cog(Admin(bot))
