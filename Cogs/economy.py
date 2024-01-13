import discord
from discord import option
from discord.ext import commands
from discord.ui import Button, View
import json
import random
import asyncio


COOLDOWN = {}


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Create an account")
    async def register(self, ctx):
        await ctx.defer()

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if author_and_guild in users:
            embed = discord.Embed(
                description=f"**Error:** You already have an active account on this server.",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        users[author_and_guild] = {"Wallet": 0, "Bank": 100, "Inventory": {}}

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        embed = discord.Embed(
            description=f"Successfully registered an account for **{ctx.author.name}**.",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Delete your account")
    async def unregister(self, ctx):
        await ctx.defer()

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Error:** You already do not have an active account on this server.",
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
                description=f"Your account has been deleted.",
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        async def no_button_callback(interaction: discord.Interaction):
            embed_ = discord.Embed(
                description=f"Account deletion cancelled.",
                color=discord.Color.dark_red(),
            )
            view.remove_item(yes_button), view.remove_item(no_button)
            await interaction.response.edit_message(embed=embed_, view=view)

        yes_button.callback, no_button.callback = yes_button_callback, no_button_callback
        view = View(timeout=None)
        view.add_item(yes_button), view.add_item(no_button)

        embed = discord.Embed(
            description=f"Are you sure you wish to delete your account?",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed, view=view)

    @commands.slash_command(description="Displays the user's current balance")
    @option("user", description="The user whose account balance you wish to see", required=False)
    async def balance(self, ctx, user: discord.User = None):
        await ctx.defer()

        if not user:
            author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"
        else:
            author_and_guild = f"{user.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if not user and author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Note:** Please create an account first using the `register` command.",
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Error:** The specified user has not opened an account.",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        user_inventory = []
        for item in users[author_and_guild]["Inventory"]:
            user_inventory.append(f"{item} [**{users[author_and_guild]['Inventory'][item]}**]")

        embed = discord.Embed(
            title=f"Balance of {ctx.author.name if not user else user.name}",
            description=f"**Wallet:** {users[author_and_guild]['Wallet']} ¤ - "
                        f"**Bank:** {users[author_and_guild]['Bank']} ¤\n"
                        f"**Net:** {users[author_and_guild]['Wallet'] + users[author_and_guild]['Bank']} ¤\n"
                        f"**Items:** "
                        f"{', '.join(user_inventory) if len(users[author_and_guild]['Inventory']) > 0 else None}",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Beg for a chance to gain credits")
    async def beg(self, ctx):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)
      
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Note:** Please create an account first using the `register` command.",
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return

        beg_amount = random.randrange(-10, 36)

        happenings_pos = [
            f"You have a successful day of begging and gain **{beg_amount}** ¤.",
            f"Just another day of being a beggar. You gain **{beg_amount}** ¤.",
            f"Some guy drops his wallet in front of you. You find **{beg_amount}** ¤ inside.",
            f"Someone felt bad for you. You gain a donation of **{beg_amount}** ¤."
        ]
        happenings_neu = [
            "You attempt begging at a quiet street. No one goes by all day, and you gain nothing.",
            "Your attempts at begging are in vain, and the whole day goes by without anyone giving you any credits."
        ]
        happenings_neg = [
            f"You try to beg for credits in a rough neighborhood and get stabbed by another beggar. "
            f"You use **{beg_amount}** ¤ to pay for medical bills.",
            f"You're begging for credits on a street corner when suddenly someone storms you and steals your "
            f"credits. You lose **{beg_amount}** ¤.",
        ]

        rand_happenings_pos = random.choice(happenings_pos)
        rand_happenings_neg = random.choice(happenings_neg)
        rand_happenings_neu = random.choice(happenings_neu)

        if COOLDOWN[author_and_guild][1] == 0:
            if beg_amount < 0:
                embed = discord.Embed(
                    description=f"{rand_happenings_neg}",
                    color=discord.Color.red(),
                )
                users[author_and_guild]["Wallet"] += beg_amount
            elif beg_amount == 0:
                embed = discord.Embed(
                    description=f"{rand_happenings_neu}",
                    color=discord.Color.dark_blue(),
                )
            else:
                embed = discord.Embed(
                    description=f"{rand_happenings_pos}",
                    color=discord.Color.green(),
                )
                users[author_and_guild]["Wallet"] += beg_amount
        else:
            embed = discord.Embed(
                description=f"**Error:** Your `beg` command is on a cooldown "
                            f"(**{120 - COOLDOWN[author_and_guild][1]} s**).",
                color=discord.Color.red(),
            )
        await ctx.followup.send(embed=embed)

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        while COOLDOWN[author_and_guild][1] != 120:
            await asyncio.sleep(1)
            COOLDOWN[author_and_guild][1] += 1
            continue

        if COOLDOWN[author_and_guild][1] == 120:
            COOLDOWN[author_and_guild][1] = 0

    @commands.slash_command(description="Deposits the specified amount to the user's bank")
    @option("deposit", description="The amount of credits you wish to deposit to your account", required=True)
    async def deposit(self, ctx, amount: int):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Note:** Please create an account first using the `register` command.",
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif not users[author_and_guild]["Wallet"] <= 0:
            embed = discord.Embed(
                description=f"**Error:** Nothing to deposit.",
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
            description=f"Successfully deposited **{amount}** ¤ to your bank.",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Withdraws the specified amount from the user's bank")
    @option("withdraw", description="The amount of credits you wish to withdraw from your account", required=True)
    async def withdraw(self, ctx, amount: int):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Note:** Please create an account first using the `register` command.",
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif users[author_and_guild]["Bank"] <= 0:
            embed = discord.Embed(
                description=f"**Error:** Nothing to withdraw.",
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
            description=f"Successfully withdrew **{amount}** ¤ from your bank.",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Rob another user for a chance to gain credits")
    @option("user", description="The user you wish to rob from", required=True)
    async def rob(self, ctx, user: discord.User):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"
        victim_and_guild = f"{user.id}-{ctx.guild.id}"

        if author_and_guild not in users:
            embed = discord.Embed(
                description=f"**Note:** Please create an account first using the `register` command.",
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif victim_and_guild not in users:
            embed = discord.Embed(
                description=f"**Error:** The specified user has not opened an account.",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif user.name == ctx.author.name:
            embed = discord.Embed(
                description=f"**Error:** You cannot rob yourself.",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return
        elif users[victim_and_guild]["Wallet"] <= 0:
            embed = discord.Embed(
                description=f"**Error:** The person you're trying to rob does not have any credits in their wallet.",
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        if COOLDOWN[author_and_guild][2] == 0:
            if users[victim_and_guild]["Wallet"] < 250:
                rob_amount = random.randrange(-50, users[victim_and_guild]["Wallet"] + 1)
            else:
                rob_amount = random.randrange(-100, users[victim_and_guild]["Wallet"] + 1)

            if rob_amount > 0:
                embed = discord.Embed(
                    description=f"You manage to rob **{rob_amount}** ¤ from **{user.name}**.",
                    color=discord.Color.green(),
                )
                users[author_and_guild]["Wallet"] += rob_amount
                users[victim_and_guild]["Wallet"] -= rob_amount
            elif rob_amount == 0:
                embed = discord.Embed(
                    description=f"Your attempt to rob credits from **{user.name}** is unsuccessful. "
                                f"You gain nothing.",
                    color=discord.Color.dark_blue(),
                )
            else:
                embed = discord.Embed(
                    description=f"You attempt to rob credits from **{user.name}**, but get caught in the act. "
                                f"You're fined **{rob_amount}** ¤.",
                    color=discord.Color.red(),
                )
                await ctx.followup.send(embed=embed)

                users[author_and_guild]["Wallet"] += rob_amount
        else:
            embed = discord.Embed(
                description=f"**Error:** Your `rob` command is on a cooldown "
                            f"(**{120 - COOLDOWN[author_and_guild][2]} s**).",
                color=discord.Color.red(),
            )
        await ctx.followup.send(embed=embed)

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        while COOLDOWN[author_and_guild][2] != 120:
            await asyncio.sleep(1)
            COOLDOWN[author_and_guild][2] += 1
            continue

        if COOLDOWN[author_and_guild][2] == 120:
            COOLDOWN[author_and_guild][2] = 0

    @commands.slash_command(description="Displays the top 5 richest players on the server")
    async def leaderboard(self, ctx):
        await ctx.defer()

        leaderboard = {"IDs": [], "SortedUsers": [], "NameAndBalance": {}, "Values": [], "Joined": ""}

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        for user in users:
            if int(user.split("-")[1]) == ctx.guild.id:
                leaderboard["IDs"].append(user)

        if len(leaderboard["IDs"]) == 0:
            embed = discord.Embed(
                title="Official ShifuBot leaderboard",
                description="No one has opened an account on this server.",
                color=discord.Color.dark_gold(),
            )
            try:
                embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)
            except AttributeError:
                embed.set_author(name=ctx.guild.name)
            await ctx.followup.send(embed=embed)
            return
        elif len(leaderboard["IDs"]) > 5:
            end_point = 5
        else:
            end_point = len(leaderboard)

        for user in leaderboard["IDs"][:end_point + 1]:
            fetched_user = await self.bot.fetch_user(int(user.split("-")[0]))
            leaderboard["NameAndBalance"][fetched_user.name] = users[user]["Wallet"] + users[user]["Bank"]

        leaderboard["SortedUsers"] = sorted(leaderboard["NameAndBalance"].items(), key=lambda x: x[1], reverse=True)

        for index, user in enumerate(leaderboard["SortedUsers"]):
            leaderboard["Values"].append(f"[**{index + 1}**] {user[0]} - {user[1]} ¤")

        leaderboard["Joined"] = "\n".join(leaderboard["Values"])

        embed = discord.Embed(
            description=f"{leaderboard['Joined']}",
            color=discord.Color.dark_gold(),
        )
        try:
            embed.set_author(name=f"{ctx.guild.name} - Leaderboard", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"{ctx.guild.name} - Leaderboard")
        await ctx.followup.send(embed=embed)

    @beg.before_invoke
    @rob.before_invoke
    async def ensure_cooldown(self, ctx):
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in COOLDOWN:
            COOLDOWN[author_and_guild] = {1: 0, 2: 0}


def setup(bot):
    bot.add_cog(Economy(bot))
