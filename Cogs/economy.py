import discord
from discord.ext import commands
from discord.ui import Button, View
import json
import random
import time


class Economy(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.cooldown = {}
        self.users = {}
        self.gui = {}
        self.views = {}

    async def resolve_gui_callback(self, ctx: discord.ApplicationContext, gui_element: str):
        async def yes_callback(interaction: discord.Interaction):
            author_and_guild = f"{interaction.user.id}-{ctx.guild.id}"
            del self.users[ctx.guild.id][author_and_guild]

            with open("Data/economics.json", "w") as economy_file:
                json.dump(self.users[ctx.guild.id], economy_file, indent=4)

            embed = discord.Embed(
                description=f"Successfully unregistered an account for **{interaction.user.name}**.",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        async def no_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                description=f"Canceled unregistering account for **{interaction.user.name}**.",
                color=discord.Color.dark_red()
            )
            await interaction.response.edit_message(embed=embed, view=None)

        callbacks = {
            "yes": yes_callback,
            "no": no_callback
        }
        return callbacks[gui_element]

    async def transfer(self, ctx: discord.ApplicationContext, amount: int, deposit: bool = False):
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"
        transfer_source = "wallet" if deposit else "bank"
        transfer_target = "bank" if deposit else "wallet"

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        if author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** User has not registered an account.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        elif self.users[ctx.guild.id][author_and_guild][transfer_source] <= 0:
            embed = discord.Embed(
                description=f"**Error:** Nothing to {'deposit' if deposit else 'withdraw'}.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        amount = min(max(amount, 0), self.users[ctx.guild.id][author_and_guild][transfer_source])
        self.users[ctx.guild.id][author_and_guild][transfer_source] -= amount
        self.users[ctx.guild.id][author_and_guild][transfer_target] += amount

        with open("Data/economics.json", "w") as economy_file:
            json.dump(self.users[ctx.guild.id], economy_file, indent=4)

        transfer_message = f"Successfully deposited **{amount}** ¤ to your bank." if deposit else \
            f"Successfully withdrew **{amount}** ¤ from your bank."

        embed = discord.Embed(
            description=transfer_message,
            color=discord.Color.dark_green()
        )
        await ctx.respond(embed=embed)

    async def handle_action(self, ctx: discord.ApplicationContext, author_id: int, amount: int, victim_id: int = None):
        author_and_guild = f"{author_id}-{ctx.guild.id}"
        victim_and_guild = f"{victim_id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        if author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** You have not registered an account.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return False
        elif victim_id and victim_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** User has not registered an account.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return False
        elif author_and_guild == victim_and_guild:
            embed = discord.Embed(
                description="**Error:** You cannot rob yourself.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return False

        elapsed_beg_cooldown, elapsed_rob_cooldown = await self.count_cooldowns(ctx)

        if not victim_id:
            if not elapsed_beg_cooldown or elapsed_beg_cooldown >= 120:
                self.cooldown[ctx.guild.id][ctx.author.id]["beg"] = time.time()
            else:
                embed = discord.Embed(
                    description=f"**Error:** Your `beg` command is on cooldown (**{120 - elapsed_beg_cooldown}** s).",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return False
        else:
            if not elapsed_rob_cooldown or elapsed_rob_cooldown >= 120:
                self.cooldown[ctx.guild.id][ctx.author.id]["rob"] = time.time()
            else:
                embed = discord.Embed(
                    description=f"**Error:** Your `rob` command is on cooldown (**{120 - elapsed_rob_cooldown}** s).",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return False

        self.users[ctx.guild.id][author_and_guild]["wallet"] += amount

        if victim_id:
            self.users[ctx.guild.id][victim_and_guild]["wallet"] -= amount

        with open("Data/economics.json", "w") as economy_file:
            json.dump(self.users[ctx.guild.id], economy_file, indent=4)

        return True

    async def get_total_balance(self, ctx: discord.ApplicationContext, user_id: int):
        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        author_and_guild = f"{user_id}-{ctx.guild.id}"

        return self.users[ctx.guild.id][author_and_guild]["wallet"] + self.users[ctx.guild.id][author_and_guild]["bank"]

    async def count_cooldowns(self, ctx: discord.ApplicationContext):
        elapsed_beg_cooldown = int(time.time() - self.cooldown[ctx.guild.id][ctx.author.id]["beg"]) if \
            self.cooldown[ctx.guild.id][ctx.author.id]["beg"] else None
        elapsed_rob_cooldown = int(time.time() - self.cooldown[ctx.guild.id][ctx.author.id]["rob"]) if \
            self.cooldown[ctx.guild.id][ctx.author.id]["rob"] else None

        return elapsed_beg_cooldown, elapsed_rob_cooldown

    @commands.slash_command(description="Create an account")
    async def register(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        if author_and_guild in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** An account already exists for this user.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.users[ctx.guild.id][author_and_guild] = {"wallet": 0, "bank": 100}

        with open("Data/economics.json", "w") as economy_file:
            json.dump(self.users[ctx.guild.id], economy_file, indent=4)

        embed = discord.Embed(
            description=f"Successfully registered an account for **{ctx.author.name}**",
            color=discord.Color.dark_green()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Delete your account")
    async def unregister(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        if author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** An account already does not exist for this user.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        embed = discord.Embed(
            description=f"Are you sure you wish to delete your account on **{ctx.guild.name}**?",
            color=discord.Color.dark_green()
        )
        await ctx.respond(embed=embed, view=self.views[ctx.guild.id])

    @commands.slash_command(description="Displays the user's current balance")
    @discord.option(name="user", description="The user whose account balance you wish to see", required=False)
    async def balance(self, ctx: discord.ApplicationContext, user: discord.User = None):
        await ctx.defer()

        author_and_guild = f"{ctx.author.id if not user else user.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        if author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description=f"**Error:** {'User has' if user else 'You have'} not registered an account.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        user_info = self.users[ctx.guild.id][author_and_guild]
        total_balance = await self.get_total_balance(ctx, ctx.author.id if not user else user.id)

        embed = discord.Embed(
            description=f"**Balance of {ctx.author.name if not user else user.name}**\n\n**Wallet:** "
                        f"{user_info['wallet']} ¤ - **Bank:** {user_info['bank']} ¤\n**Total:** {total_balance} ¤",
            color=discord.Color.dark_green()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Deposits the specified amount to the user's bank")
    @discord.option(name="amount", description="The amount of credits you wish to deposit to your account",
                    required=True)
    async def deposit(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer()

        await self.transfer(ctx, amount, deposit=True)

    @commands.slash_command(description="Withdraws the specified amount from the user's bank")
    @discord.option(name="amount", description="The amount of credits you wish to withdraw from your account",
                    required=True)
    async def withdraw(self, ctx: discord.ApplicationContext, amount: int):
        await ctx.defer()

        await self.transfer(ctx, amount)

    @commands.slash_command(description="Beg for a chance to gain credits")
    async def beg(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        pos_msgs = ["You gain **{}** ¤ after a successful day of begging."]
        neu_msgs = ["Not a single person stops to give you money, leaving your gains at **{}** ¤."]
        neg_msgs = ["Another beggar stabs you with a rusty knife, you gain tetanus, but lose **{}** ¤."]

        amount = random.randint(-20, 50)
        beg_msg = random.choice(pos_msgs if amount > 0 else neg_msgs if amount < 0 else neu_msgs)

        if not await self.handle_action(ctx, ctx.author.id, amount):
            return

        embed = discord.Embed(
            description=beg_msg.format(amount),
            color=discord.Color.green() if amount > 0 else discord.Color.dark_red() if amount < 0 else
            discord.Color.dark_blue()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Rob another user for a chance to gain credits")
    @discord.option(name="user", description="The user you wish to rob from", required=True)
    async def rob(self, ctx: discord.ApplicationContext, user: discord.User):
        await ctx.defer()

        victim_and_guild = f"{user.id}-{ctx.guild.id}"

        pos_msgs = ["You successfully give **{}** the old one-two treatment, and lighten their wallet by **{}** ¤."]
        neu_msgs = ["You plan of robbing **{}** too long, and the opportunity passes, leaving your gains at **{}** ¤."]
        neg_msgs = ["You are caught red-handed trying to rob **{}**, and get fined **{}** ¤."]

        amount = random.randint(max(-100, -(self.users[ctx.guild.id][victim_and_guild]["wallet"] // 3)),
                                self.users[ctx.guild.id][victim_and_guild]["wallet"])
        rob_msg = random.choice(pos_msgs if amount > 0 else neg_msgs if amount < 0 else neu_msgs)

        if not await self.handle_action(ctx, ctx.author.id, amount, user.id):
            return

        embed = discord.Embed(
            description=rob_msg.format(user.name, amount),
            color=discord.Color.green() if amount > 0 else discord.Color.dark_red() if amount < 0 else
            discord.Color.dark_blue()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Displays the richest users in the guild")
    @discord.option(name="from", description="The start position of the leaderboard display", required=False)
    @discord.option(name="to", description="The end position of the leaderboard display", required=False)
    async def leaderboard(self, ctx: discord.ApplicationContext, from_: int = None, to: int = None):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        guild_users = [await self.bot.fetch_user(int(k.split("-")[0])) for k in self.users[ctx.guild.id] if
                       int(k.split("-")[1]) == ctx.guild.id]
        user_balances = [(k, await self.get_total_balance(ctx, k.id)) for k in guild_users]
        user_balances.sort(key=lambda x: x[1], reverse=True)

        from_ = max(1, min(from_, len(guild_users))) if from_ else 1
        to = max(1, min(to, len(guild_users))) if to else len(guild_users)
        from_, to = ((from_, to) if from_ < to else (to, from_)) if to != 0 else (from_, to)

        leaderboard_msg = "No one has opened an account in this guild." if not guild_users else \
            "\n".join([f"[**{i + from_}**] {user.name} - {balance} ¤"
                       for i, (user, balance) in enumerate(user_balances[from_ - 1:to])])
        addition_song_count = len(user_balances) - to - 1 + from_
        leaderboard_msg += f"\n+ **{addition_song_count}** more..." if addition_song_count else ""

        embed = discord.Embed(
            description=leaderboard_msg,
            color=discord.Color.dark_gold()
        )
        try:
            embed.set_author(name=f"{ctx.guild.name} - Leaderboard", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"{ctx.guild.name} - Leaderboard")
        await ctx.respond(embed=embed)

    @register.before_invoke
    @unregister.before_invoke
    @balance.before_invoke
    @beg.before_invoke
    @deposit.before_invoke
    @withdraw.before_invoke
    @rob.before_invoke
    @leaderboard.before_invoke
    async def ensure_dicts(self, ctx: discord.ApplicationContext):
        if ctx.guild.id not in self.users:
            with open("Data/economics.json", "r") as economy_file:
                self.users[ctx.guild.id] = json.load(economy_file)

            self.gui[ctx.guild.id] = {
                "yes": Button(style=discord.ButtonStyle.success, label="Yes", row=1),
                "no": Button(style=discord.ButtonStyle.danger, label="No", row=1)
            }
            self.views[ctx.guild.id] = View(timeout=None)
            self.cooldown[ctx.guild.id] = {}

            if ctx.author.id not in self.cooldown[ctx.guild.id]:
                self.cooldown[ctx.guild.id][ctx.author.id] = {"beg": None, "rob": None}

            for elem in self.gui[ctx.guild.id].keys():
                self.gui[ctx.guild.id][elem].callback = await self.resolve_gui_callback(ctx, elem)
                self.views[ctx.guild.id].add_item(self.gui[ctx.guild.id][elem])


def setup(bot):
    bot.add_cog(Economy(bot))
