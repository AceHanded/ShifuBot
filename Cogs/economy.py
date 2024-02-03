import discord
from discord import option
from discord.ext import commands
from discord.ui import Button, View
import json
import random
import asyncio
from Cogs.utils import get_language_strings


COOLDOWN = {}


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Create an account")
    async def register(self, ctx):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if author_and_guild in users:
            embed = discord.Embed(
                description=strings["Errors.AccountExists"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        users[author_and_guild] = {"Wallet": 0, "Bank": 100, "Inventory": {}}

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        embed = discord.Embed(
            description=strings["Economy.Register"].format(ctx.author.name),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Delete your account")
    async def unregister(self, ctx):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Errors.AlreadyNoAccount"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        yes_button = Button(style=discord.ButtonStyle.success, label="Yes", row=1)
        no_button = Button(style=discord.ButtonStyle.danger, label="No", row=1)

        async def yes_button_callback(interaction: discord.Interaction):
            del users[author_and_guild]

            with open("Data/economics.json", "w") as economy_file_:
                json.dump(users, economy_file_, indent=4)

            embed_ = discord.Embed(
                description=strings["Economy.UnregisterSuccess"],
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        async def no_button_callback(interaction: discord.Interaction):
            embed_ = discord.Embed(
                description=strings["Economy.UnregisterCancel"],
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        yes_button.callback, no_button.callback = yes_button_callback, no_button_callback
        view = View(timeout=None)
        view.add_item(yes_button), view.add_item(no_button)

        embed = discord.Embed(
            description=strings["Economy.Unregister"].format(ctx.guild.name),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed, view=view)

    @commands.slash_command(description="Displays the user's current balance")
    @option(name="user", description="The user whose account balance you wish to see", required=False)
    async def balance(self, ctx, user: discord.User = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        if not user:
            author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"
        else:
            author_and_guild = f"{user.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if not user and author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Errors.UserNoAccount"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        user_inventory = []
        for item in users[author_and_guild]["Inventory"]:
            user_inventory.append(f"{item} [**{users[author_and_guild]['Inventory'][item]}**]")

        embed = discord.Embed(
            title=strings["Economy.Balance"].format(ctx.author.name if not user else user.name),
            description=strings["Economy.BalanceDesc"].format(
                users[author_and_guild]["Wallet"], users[author_and_guild]["Bank"],
                users[author_and_guild]["Wallet"] + users[author_and_guild]["Bank"],
                ", ".join(user_inventory) if len(users[author_and_guild]["Inventory"]) > 0 else None),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Beg for a chance to gain credits")
    async def beg(self, ctx):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)
      
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif not COOLDOWN[author_and_guild][0] == 0:
            embed = discord.Embed(
                description=strings["Errors.CooldownBeg"].format(120 - COOLDOWN[author_and_guild][0]),
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        beg_amount = random.randrange(-10, 36)

        if beg_amount < 0:
            embed = discord.Embed(
                description=random.choice(strings["Beg.HappeningsNeg"]).format(beg_amount),
                color=discord.Color.red(),
            )
            users[author_and_guild]["Wallet"] += beg_amount
        elif beg_amount == 0:
            embed = discord.Embed(
                description=random.choice(strings["Beg.HappeningsNeu"]),
                color=discord.Color.dark_blue(),
            )
        else:
            embed = discord.Embed(
                description=random.choice(strings["Beg.HappeningsPos"]).format(beg_amount),
                color=discord.Color.green(),
            )
            users[author_and_guild]["Wallet"] += beg_amount
        await ctx.followup.send(embed=embed)

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        while COOLDOWN[author_and_guild][0] != 120:
            await asyncio.sleep(1)
            COOLDOWN[author_and_guild][0] += 1
            continue

        if COOLDOWN[author_and_guild][0] == 120:
            COOLDOWN[author_and_guild][0] = 0

    @commands.slash_command(description="Deposits the specified amount to the user's bank")
    @option(name="amount", description="The amount of credits you wish to deposit to your account", required=True)
    async def deposit(self, ctx, amount: int):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif users[author_and_guild]["Wallet"] <= 0:
            embed = discord.Embed(
                description=strings["Errors.NoDeposit"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        amount = min(max(amount, 0), users[author_and_guild]["Wallet"])

        users[author_and_guild]["Wallet"] -= amount
        users[author_and_guild]["Bank"] += amount

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        embed = discord.Embed(
            description=strings["Economy.Deposit"].format(amount),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Withdraws the specified amount from the user's bank")
    @option(name="amount", description="The amount of credits you wish to withdraw from your account", required=True)
    async def withdraw(self, ctx, amount: int):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif users[author_and_guild]["Bank"] <= 0:
            embed = discord.Embed(
                description=strings["Errors.NoWithdraw"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        amount = min(max(amount, 0), users[author_and_guild]["Bank"])

        users[author_and_guild]["Bank"] -= amount
        users[author_and_guild]["Wallet"] += amount

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        embed = discord.Embed(
            description=strings["Economy.Withdraw"].format(amount),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Rob another user for a chance to gain credits")
    @option(name="user", description="The user you wish to rob from", required=True)
    async def rob(self, ctx, user: discord.User):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"
        victim_and_guild = f"{user.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif victim_and_guild not in users:
            embed = discord.Embed(
                description=strings["Errors.UserNoAccount"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif user.name == ctx.author.name:
            embed = discord.Embed(
                description=strings["Errors.RobSelf"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif users[victim_and_guild]["Wallet"] <= 0:
            embed = discord.Embed(
                description=strings["Errors.RobBroke"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif not COOLDOWN[author_and_guild][1] == 0:
            embed = discord.Embed(
                description=strings["Errors.CooldownRob"].format(120 - COOLDOWN[author_and_guild][1]),
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        if users[victim_and_guild]["Wallet"] < 250:
            rob_amount = random.randrange(-50, users[victim_and_guild]["Wallet"] + 1)
        else:
            rob_amount = random.randrange(-100, users[victim_and_guild]["Wallet"] + 1)

        if rob_amount > 0:
            embed = discord.Embed(
                description=strings["Economy.RobSuccess"].format(rob_amount, user.name),
                color=discord.Color.green(),
            )
            users[author_and_guild]["Wallet"] += rob_amount
            users[victim_and_guild]["Wallet"] -= rob_amount
        elif rob_amount == 0:
            embed = discord.Embed(
                description=strings["Economy.RobNeutral"].format(user.name),
                color=discord.Color.dark_blue(),
            )
        else:
            embed = discord.Embed(
                description=strings["Economy.RobFailure"].format(user.name, rob_amount),
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)

            users[author_and_guild]["Wallet"] += rob_amount
        await ctx.followup.send(embed=embed)

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        while COOLDOWN[author_and_guild][1] != 120:
            await asyncio.sleep(1)
            COOLDOWN[author_and_guild][1] += 1
            continue

        if COOLDOWN[author_and_guild][1] == 120:
            COOLDOWN[author_and_guild][1] = 0

    @commands.slash_command(description="Displays the richest users in the guild")
    @option(name="to", description="The end position of the leaderboard display", required=False)
    async def leaderboard(self, ctx, to: int = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        leaderboard = {"IDs": [], "SortedUsers": [], "NameAndBalance": {}, "Values": [], "Joined": ""}

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        for user in users:
            if int(user.split("-")[1]) == ctx.guild.id:
                leaderboard["IDs"].append(user)

        if len(leaderboard["IDs"]) == 0:
            embed = discord.Embed(
                description=strings["Economy.LeaderboardNoAccounts"],
                color=discord.Color.dark_gold(),
            )
            try:
                embed.set_author(name=strings["Economy.Leaderboard"].format(ctx.guild.name),
                                 icon_url=ctx.guild.icon.url)
            except AttributeError:
                embed.set_author(name=strings["Economy.Leaderboard"].format(ctx.guild.name))
            await ctx.followup.send(embed=embed)
            return
        elif to:
            end_point = min(max(to, 1), len(leaderboard["IDs"]))
        elif len(leaderboard["IDs"]) > 10:
            end_point = 11
        else:
            end_point = len(leaderboard["IDs"])

        for user in leaderboard["IDs"][:end_point]:
            fetched_user = await self.bot.fetch_user(int(user.split("-")[0]))
            leaderboard["NameAndBalance"][fetched_user.name] = users[user]["Wallet"] + users[user]["Bank"]

        leaderboard["SortedUsers"] = sorted(leaderboard["NameAndBalance"].items(), key=lambda x: x[1], reverse=True)

        for index, user in enumerate(leaderboard["SortedUsers"]):
            leaderboard["Values"].append(f"[**{index + 1}**] {user[0]} - {user[1]} ¤")

            if len(leaderboard["Values"]) >= 3952:
                break

        leaderboard["Joined"] = "\n".join(leaderboard["Values"])
        additional_users = len(leaderboard["IDs"]) - len(leaderboard["Values"])

        embed = discord.Embed(
            description=f"{leaderboard['Joined']}\n"
                        f"{strings['Music.Additional'].format(additional_users) if additional_users else ''}",
            color=discord.Color.dark_gold(),
        )
        try:
            embed.set_author(name=strings["Economy.Leaderboard"].format(ctx.guild.name), icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=strings["Economy.Leaderboard"].format(ctx.guild.name))
        await ctx.followup.send(embed=embed)

    @beg.before_invoke
    @rob.before_invoke
    async def ensure_cooldown(self, ctx):
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in COOLDOWN:
            COOLDOWN[author_and_guild] = [0, 0]


def setup(bot):
    bot.add_cog(Economy(bot))
