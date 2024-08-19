import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
import random
import json
from Cogs.utils import Constants


class Game(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.users = {}
        self.messages = {}
        self.deck = {}
        self.blackjack_players = {}
        self.blackjack_bet = {}
        self.brawl_players = {}
        self.brawl_info = {}
        self.gui = {}
        self.views = {}

    def resolve_view(self, ctx: discord.ApplicationContext):
        if not self.brawl_players[ctx.guild.id] or all(k in [0, 1, 2] for k in self.brawl_players[ctx.guild.id]):
            return None

        bot_count = len([k for k in self.brawl_players[ctx.guild.id].keys() if k in [0, 1, 2]])

        if 0 < bot_count < 3:
            return self.views[ctx.guild.id]["brawl_all"]
        if bot_count == 0:
            return self.views[ctx.guild.id]["brawl_no_remove"]
        else:
            return self.views[ctx.guild.id]["brawl_no_add"]

    @staticmethod
    async def create_deck():
        random.shuffle(deck := [f"{value} of {suit}" for value in Constants.CARD_VALUE
                                for suit in Constants.CARD_SUIT.keys()])
        return deck

    async def resolve_gui_callback(self, ctx: discord.ApplicationContext, gui_element: str):
        async def blackjack_hit_callback(interaction: discord.Interaction):
            card = self.deck[ctx.guild.id][interaction.user.id].pop(0)
            self.blackjack_players[ctx.guild.id][interaction.user.id].append(card)

            joined_player_cards = "\n".join(self.blackjack_players[ctx.guild.id][interaction.user.id])
            joined_dealer_cards = "\n".join(self.blackjack_players[ctx.guild.id][0])
            player_total = await self.calculate_total(ctx, interaction.user.id)
            dealer_total = await self.calculate_total(ctx, 0)

            embed = discord.Embed(
                description=f"**Your hand:**\n{joined_player_cards}\n**Total value:** {player_total}\n\n"
                            f"**Dealer's hand:**\n{joined_dealer_cards}\n**Total value:** {dealer_total}",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=None if player_total >= 21 else
                                                    self.views[ctx.guild.id]["blackjack"])

            if player_total == 21:
                with open("Data/economics.json", "r") as economy_file:
                    self.users[ctx.guild.id] = json.load(economy_file)

                author_and_guild = f"{interaction.user.id}-{ctx.guild.id}"
                winnings = self.blackjack_bet[ctx.guild.id][interaction.user.id] * 2

                if author_and_guild in self.users[ctx.guild.id]:
                    self.users[ctx.guild.id][author_and_guild]["wallet"] += winnings

                    with open("Data/economics.json", "w") as economy_file:
                        json.dump(self.users[ctx.guild.id], economy_file, indent=4)

                embed = discord.Embed(
                    description=f"You have won via blackjack. Congratulations, your wallet just got bigger by "
                                f"**{winnings}** ¤.",
                    color=discord.Color.dark_gold()
                )
                await interaction.followup.send(embed=embed)
                await self.blackjack_cleanup(ctx, interaction.user.id)
            elif player_total > 21:
                embed = discord.Embed(
                    description=f"Dealer has won via you overdrawing. Better luck next time, you have lost "
                                f"**{self.blackjack_bet[ctx.guild.id][interaction.user.id]}** ¤.",
                    color=discord.Color.dark_red()
                )
                await interaction.followup.send(embed=embed)
                await self.blackjack_cleanup(ctx, interaction.user.id)

        async def blackjack_stand_callback(interaction: discord.Interaction):
            joined_player_cards = "\n".join(self.blackjack_players[ctx.guild.id][interaction.user.id])
            player_total = await self.calculate_total(ctx, interaction.user.id)
            dealer_total = await self.calculate_total(ctx, 0)

            while dealer_total < player_total:
                card = self.deck[ctx.guild.id][interaction.user.id].pop(0)

                if "?" in self.blackjack_players[ctx.guild.id][0]:
                    self.blackjack_players[ctx.guild.id][0][self.blackjack_players[ctx.guild.id][0].index("?")] = card
                else:
                    await asyncio.sleep(1)
                    self.blackjack_players[ctx.guild.id][0].append(card)

                joined_dealer_cards = "\n".join(self.blackjack_players[ctx.guild.id][0])
                dealer_total = await self.calculate_total(ctx, 0)

                embed = discord.Embed(
                    description=f"**Your hand:**\n{joined_player_cards}\n**Total value:** {player_total}\n\n"
                                f"**Dealer's hand:**\n{joined_dealer_cards}\n**Total value:** {dealer_total}",
                    color=discord.Color.dark_green()
                )
                try:
                    await interaction.response.edit_message(embed=embed, view=None)
                except discord.errors.InteractionResponded:
                    await self.messages[ctx.guild.id]["blackjack"][interaction.user.id].edit(embed=embed)

            if dealer_total == 21:
                embed = discord.Embed(
                    description=f"Dealer has won via blackjack. Better luck next time, you have lost "
                                f"**{self.blackjack_bet[ctx.guild.id][interaction.user.id]}** ¤.",
                    color=discord.Color.dark_red()
                )
                await interaction.followup.send(embed=embed)
            elif dealer_total > 21:
                with open("Data/economics.json", "r") as economy_file:
                    self.users[ctx.guild.id] = json.load(economy_file)

                author_and_guild = f"{interaction.user.id}-{ctx.guild.id}"
                winnings = self.blackjack_bet[ctx.guild.id][interaction.user.id] * 2

                if author_and_guild in self.users[ctx.guild.id]:
                    self.users[ctx.guild.id][author_and_guild]["wallet"] += winnings

                    with open("Data/economics.json", "w") as economy_file:
                        json.dump(self.users[ctx.guild.id], economy_file, indent=4)

                embed = discord.Embed(
                    description=f"You have won via dealer overdrawing. Congratulations, your wallet just got bigger by "
                                f"**{self.blackjack_bet[ctx.guild.id][interaction.user.id]}** ¤.",
                    color=discord.Color.dark_gold()
                )
                await interaction.followup.send(embed=embed)
            elif dealer_total == player_total:
                with open("Data/economics.json", "r") as economy_file:
                    self.users[ctx.guild.id] = json.load(economy_file)

                author_and_guild = f"{interaction.user.id}-{ctx.guild.id}"
                winnings = self.blackjack_bet[ctx.guild.id][interaction.user.id]

                if author_and_guild in self.users[ctx.guild.id]:
                    self.users[ctx.guild.id][author_and_guild]["wallet"] += winnings

                    with open("Data/economics.json", "w") as economy_file:
                        json.dump(self.users[ctx.guild.id], economy_file, indent=4)

                embed = discord.Embed(
                    description=f"You have tied with the dealer. Your wallet has been refunded **{winnings}** ¤.",
                    color=discord.Color.blue()
                )
                await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(
                    description=f"Dealer has won via higher value cards. Better luck next time, you have lost "
                                f"**{self.blackjack_bet[ctx.guild.id][interaction.user.id]}** ¤.",
                    color=discord.Color.dark_red()
                )
                await interaction.followup.send(embed=embed)

            await self.blackjack_cleanup(ctx, interaction.user.id)

        async def blackjack_reset_callback(interaction: discord.Interaction):
            await self.blackjack_cleanup(ctx, interaction.user.id)
            await interaction.response.edit_message(view=None)

        async def brawl_begin_callback(interaction: discord.Interaction):
            if len(self.brawl_players[ctx.guild.id]) < 2:
                embed = discord.Embed(
                    description="**Error:** Cannot start the brawl due to insufficient amount of brawlers.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await interaction.response.edit_message(view=None)

            player_multiplier = len(self.brawl_players[ctx.guild.id])
            actions = ["**[1]** The brawl has begun!"]

            embed = discord.Embed(
                title="Brawl log",
                description=actions[0],
                color=discord.Color.dark_green(),
            )
            msg = await interaction.followup.send(embed=embed)

            while len(self.brawl_players[ctx.guild.id]) > 1:
                await asyncio.sleep(1)

                random_id = random.choice(list(self.brawl_players[ctx.guild.id].keys()))
                random_player = self.brawl_players[ctx.guild.id][random_id]["name"]
                random_dmg = random.randrange(11)
                self.brawl_players[ctx.guild.id][random_id]["hp"] -= random_dmg
                filtered = {ctx.guild.id: []}

                for player_id in self.brawl_players[ctx.guild.id]:
                    if player_id != random_id:
                        filtered[ctx.guild.id].append(player_id)

                if random_dmg == 0:
                    random_filtered = random.choice(filtered[ctx.guild.id])
                    action_message = (f"**{self.brawl_players[ctx.guild.id][random_filtered]['name']}** attacks "
                                      f"**{random_player}** via {random.choice(Constants.ATTACKS)}, but misses and "
                                      f"deals **{random_dmg}** damage, leaving them with "
                                      f"**{self.brawl_players[ctx.guild.id][random_id]['hp']}** health points.")
                    actions.append(f"[**{len(actions) + 1}**] {action_message}")
                elif 0 < random_dmg < 10:
                    random_filtered = random.choice(filtered[ctx.guild.id])
                    action_message = (f"**{self.brawl_players[ctx.guild.id][random_filtered]['name']}** deals "
                                      f"**{random_dmg}** damage to **{random_player}** via "
                                      f"{random.choice(Constants.ATTACKS)}, leaving them with "
                                      f"**{self.brawl_players[ctx.guild.id][random_id]['hp']}** health points.")
                    actions.append(f"[**{len(actions) + 1}**] {action_message}")
                else:
                    random_filtered = random.choice(filtered[ctx.guild.id])
                    action_message = (f"**{self.brawl_players[ctx.guild.id][random_filtered]['name']}** spots a "
                                      f"*critical* weakness and deals **{random_dmg}** damage to **{random_player}** "
                                      f"via {random.choice(Constants.ATTACKS)}, leaving them with "
                                      f"**{self.brawl_players[ctx.guild.id][random_id]['hp']}** health points, "
                                      f"and a very sore {random.choice(Constants.SPOTS)}.")
                    actions.append(f"[**{len(actions) + 1}**] {action_message}")

                if self.brawl_players[ctx.guild.id][random_id]["hp"] <= 0:
                    actions.append(f"[**{len(actions) + 1}X**] **{random_player}** has fallen.")
                    self.brawl_players[ctx.guild.id].pop(random_id)
                    color_choice = discord.Color.dark_red()
                else:
                    color_choice = discord.Color.dark_green() if 0 < random_dmg < 10 else discord.Color.dark_blue() if \
                        random_dmg == 0 else discord.Color.purple()

                embed = discord.Embed(
                    title="Brawl log",
                    description="\n".join(actions),
                    color=color_choice
                )
                await msg.edit(embed=embed)

            winner_id = list(self.brawl_players[ctx.guild.id].keys())[0]
            winner_and_guild = f"{winner_id}-{ctx.guild.id}"

            with open("Data/economics.json", "r") as economy_file:
                self.users[ctx.guild.id] = json.load(economy_file)

            if winner_and_guild in self.users[ctx.guild.id]:
                winnings = (random.randrange(10, 25) +
                            (self.brawl_info[ctx.guild.id]["bet"] * player_multiplier))

                self.users[ctx.guild.id][winner_and_guild]["wallet"] += winnings

                with open("Data/economics.json", "w") as economy_file:
                    json.dump(self.users[ctx.guild.id], economy_file, indent=4)

                embed = discord.Embed(
                    description=f"**{self.brawl_players[ctx.guild.id][winner_id]['name']}** has won the "
                                f"**{self.brawl_info[ctx.guild.id]['scene']}**, and is crowned as champion. They have "
                                f"also found **{winnings}** ¤ in the pockets of the fallen brawlers.",
                    color=discord.Color.dark_gold()
                )
            else:
                embed = discord.Embed(
                    description=f"**{self.brawl_players[ctx.guild.id][winner_id]['name']}** has won the "
                                f"**{self.brawl_info[ctx.guild.id]['scene']}**, and is crowned as champion. In the "
                                f"future they may consider using the `register` command, to collect their winnings.",
                    color=discord.Color.dark_gold()
                )
            await interaction.followup.send(embed=embed)

            await self.brawl_cleanup(ctx)

        async def brawl_join_callback(interaction: discord.Interaction):
            with open("Data/economics.json", "r") as economy_file:
                self.users[ctx.guild.id] = json.load(economy_file)

            user_and_guild = f"{interaction.user.id}-{ctx.guild.id}"

            if interaction.user.id in self.brawl_players[ctx.guild.id]:
                embed = discord.Embed(
                    description="**Error:** You are already participating in the brawl.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            elif self.brawl_info[ctx.guild.id]["bet"] and user_and_guild not in self.users[ctx.guild.id]:
                embed = discord.Embed(
                    description="**Note:** Please create an account using the `register` command to participate in "
                                "bets.",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            elif self.brawl_info[ctx.guild.id]["bet"] and user_and_guild in self.users[ctx.guild.id] and \
                    self.users[ctx.guild.id][user_and_guild]["wallet"] < self.brawl_info[ctx.guild.id]["bet"]:
                embed = discord.Embed(
                    description="**Error:** Your wallet balance is too low to place this bet.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            self.brawl_players[ctx.guild.id][interaction.user.id] = {"hp": 20, "name": interaction.user.name}

            joined_brawlers = ", ".join([self.brawl_players[ctx.guild.id][id_]["name"] for id_ in
                                         self.brawl_players[ctx.guild.id]])

            self.brawl_info[ctx.guild.id]["join_log"].append(f"**{interaction.user.name}** has joined the brawl.")
            joined_join_messages_ = "\n".join(self.brawl_info[ctx.guild.id]["join_log"])

            if user_and_guild in self.users[ctx.guild.id]:
                self.users[ctx.guild.id][user_and_guild]["wallet"] -= self.brawl_info[ctx.guild.id]["bet"]

            with open("Data/economics.json", "w") as economy_file:
                json.dump(self.users[ctx.guild.id], economy_file, indent=4)

            embed = discord.Embed(
                title=self.brawl_info[ctx.guild.id]["scene"],
                description=f"Uh-oh. Someone didn't like someone's face and now a classic brawl is about to break out. "
                            f"Seems like rules won't apply in this match.\n\n**Current brawlers:** {joined_brawlers} "
                            f"[**{len(self.brawl_players[ctx.guild.id])}**]\n**Required bet:** "
                            f"{self.brawl_info[ctx.guild.id]['bet']} ¤\n\n**Join log:**\n{joined_join_messages_}",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=self.resolve_view(ctx))

        async def brawl_add_callback(interaction: discord.Interaction):
            nick_former = ["Harold", "El", "Bob", "Whatsisface", "Lightning", "Jake", "Ratchet", "Gaylord", "Nyan"]
            nick_latter = ["the Midget Slayer", "Jefe", "Primo", "Worthington", "Buildman", "Droid mk I", "the Chosen",
                           "Bot", "Shoehorn", "Caneman", "Nucleus"]
            nickname = f"{random.choice(nick_former)} {random.choice(nick_latter)}"

            next((self.brawl_players[ctx.guild.id].update({i: {"hp": 20, "name": nickname}}) for i in range(3)
                  if i not in self.brawl_players[ctx.guild.id]), None)

            joined_brawlers = ", ".join([self.brawl_players[ctx.guild.id][id_]["name"] for id_ in
                                         self.brawl_players[ctx.guild.id]])

            self.brawl_info[ctx.guild.id]["join_log"].append(f"**{nickname}** has joined the brawl.")
            joined_join_messages_ = "\n".join(self.brawl_info[ctx.guild.id]["join_log"])

            embed = discord.Embed(
                title=self.brawl_info[ctx.guild.id]["scene"],
                description=f"Uh-oh. Someone didn't like someone's face and now a classic brawl is about to break out. "
                            f"Seems like rules won't apply in this match.\n\n**Current brawlers:** {joined_brawlers} "
                            f"[**{len(self.brawl_players[ctx.guild.id])}**]\n**Required bet:** "
                            f"{self.brawl_info[ctx.guild.id]['bet']} ¤\n\n**Join log:**\n{joined_join_messages_}",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=self.resolve_view(ctx))

        async def brawl_remove_callback(interaction: discord.Interaction):
            bot = next((self.brawl_players[ctx.guild.id].pop(i) for i in range(3)
                        if i in self.brawl_players[ctx.guild.id]), None)

            joined_brawlers = ", ".join([self.brawl_players[ctx.guild.id][id_]["name"] for id_ in
                                         self.brawl_players[ctx.guild.id]])

            self.brawl_info[ctx.guild.id]["join_log"].append(f"**{bot['name']}** has been removed from the site of the "
                                                             f"brawl.")
            joined_join_messages_ = "\n".join(self.brawl_info[ctx.guild.id]["join_log"])

            embed = discord.Embed(
                title=self.brawl_info[ctx.guild.id]["scene"],
                description=f"Uh-oh. Someone didn't like someone's face and now a classic brawl is about to break out. "
                            f"Seems like rules won't apply in this match.\n\n**Current brawlers:** {joined_brawlers} "
                            f"[**{len(self.brawl_players[ctx.guild.id])}**]\n**Required bet:** "
                            f"{self.brawl_info[ctx.guild.id]['bet']} ¤\n\n**Join log:**\n{joined_join_messages_}",
                color=discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=self.resolve_view(ctx))

        async def brawl_cancel_callback(interaction: discord.Interaction):
            with open("Data/economics.json", "r") as economy_file:
                self.users[ctx.guild.id] = json.load(economy_file)

            user_and_guild = f"{interaction.user.id}-{ctx.guild.id}"

            if interaction.user.id not in self.brawl_players[ctx.guild.id]:
                embed = discord.Embed(
                    description="**Error:** You are already not participating in the brawl.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            self.brawl_players[ctx.guild.id].pop(interaction.user.id)

            no_players = not self.brawl_players[ctx.guild.id] or \
                all(k in [0, 1, 2] for k in self.brawl_players[ctx.guild.id])

            joined_brawlers = ", ".join([self.brawl_players[ctx.guild.id][id_]["name"] for id_ in
                                         self.brawl_players[ctx.guild.id]])

            content_msg = (f"**{self.brawl_info[ctx.guild.id]['scene']} has been cancelled.**" if no_players
                           else f"**Current brawlers:** {joined_brawlers} [**{len(self.brawl_players[ctx.guild.id])}**]"
                                f"\n**Required bet:** {self.brawl_info[ctx.guild.id]['bet']} ¤")

            self.brawl_info[ctx.guild.id]["join_log"].append(f"**{interaction.user.name}** became scared and ran away.")
            joined_join_messages_ = "\n".join(self.brawl_info[ctx.guild.id]["join_log"])

            if user_and_guild in self.users[ctx.guild.id]:
                self.users[ctx.guild.id][user_and_guild]["wallet"] += self.brawl_info[ctx.guild.id]["bet"]

            with open("Data/economics.json", "w") as economy_file:
                json.dump(self.users[ctx.guild.id], economy_file, indent=4)

            embed = discord.Embed(
                title=self.brawl_info[ctx.guild.id]["scene"],
                description=f"Uh-oh. Someone didn't like someone's face and now a classic brawl is about to break out. "
                            f"Seems like rules won't apply in this match.\n\n{content_msg}\n\n**Join log:**\n"
                            f"{joined_join_messages_}",
                color=discord.Color.dark_red() if no_players else discord.Color.dark_green()
            )
            await interaction.response.edit_message(embed=embed, view=self.resolve_view(ctx))

            if no_players:
                await self.brawl_cleanup(ctx)

        async def brawl_reset_callback(interaction: discord.Interaction):
            await self.brawl_cleanup(ctx)
            await interaction.response.edit_message(view=None)

        callbacks = {
            "blackjack_hit": blackjack_hit_callback,
            "blackjack_stand": blackjack_stand_callback,
            "blackjack_reset": blackjack_reset_callback,
            "brawl_begin": brawl_begin_callback,
            "brawl_join": brawl_join_callback,
            "brawl_add": brawl_add_callback,
            "brawl_remove": brawl_remove_callback,
            "brawl_cancel": brawl_cancel_callback,
            "brawl_reset": brawl_reset_callback
        }
        return callbacks[gui_element]

    async def blackjack_cleanup(self, ctx: discord.ApplicationContext, user_id: int = None):
        try:
            await self.messages[ctx.guild.id]["blackjack"][user_id].edit(view=None)
        except (discord.NotFound, discord.HTTPException, AttributeError):
            pass

        for dictionary in [self.messages, self.deck, self.blackjack_players, self.blackjack_bet]:
            if dictionary == self.messages and ctx.guild.id in dictionary:
                dictionary[ctx.guild.id]["blackjack"][user_id] = None
            elif user_id and ctx.guild.id in dictionary:
                del dictionary[ctx.guild.id][user_id]
            elif ctx.guild.id in dictionary:
                del dictionary[ctx.guild.id]

    async def brawl_cleanup(self, ctx: discord.ApplicationContext):
        try:
            await self.messages[ctx.guild.id]["brawl"].edit(view=None)
        except (discord.NotFound, discord.HTTPException, AttributeError):
            pass

        for dictionary in [self.messages, self.brawl_players, self.brawl_info]:
            if dictionary == self.messages and ctx.guild.id in dictionary:
                dictionary[ctx.guild.id]["brawl"] = None
            elif ctx.guild.id in dictionary:
                del dictionary[ctx.guild.id]

    async def calculate_total(self, ctx: discord.ApplicationContext, user_id: int):
        total, ace_count = 0, 0

        for card in self.blackjack_players[ctx.guild.id][user_id]:
            value = card.split(" of ")[0]

            if value.isdigit():
                total += int(value)
            elif value in ["Jack", "Queen", "King"]:
                total += 10
            elif value == "?":
                total += 0
            else:
                total += 11
                ace_count += 1

        while total > 21 and ace_count:
            total -= 10
            ace_count -= 1

        return total

    @commands.slash_command(description="Create a game of brawl")
    @discord.option(name="bet", description="The amount of credits you wish to bet on a game of brawl", required=False)
    async def brawl(self, ctx: discord.ApplicationContext, bet: int = 0):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        author_and_guild = f"{ctx.user.id}-{ctx.guild.id}"

        if self.brawl_players[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** An active brawl already exists.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, view=self.views[ctx.guild.id]["brawl_reset"])
            return
        elif bet and author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Note:** Please create an account using the `register` command to place bets.",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return
        elif bet and author_and_guild in self.users[ctx.guild.id] and \
                self.users[ctx.guild.id][author_and_guild]["wallet"] < bet:
            embed = discord.Embed(
                description="**Error:** Your wallet balance is too low to place this bet.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.brawl_info[ctx.guild.id]["bet"] = bet
        self.brawl_info[ctx.guild.id]["scene"] = random.choice(Constants.SCENES)

        self.brawl_players[ctx.guild.id][ctx.author.id] = {"hp": 20, "name": ctx.author.name}

        joined_brawlers = ", ".join([self.brawl_players[ctx.guild.id][id_]["name"] for id_ in
                                     self.brawl_players[ctx.guild.id]])

        self.brawl_info[ctx.guild.id]["join_log"].append(f"**{ctx.author.name}** has joined the brawl.")
        joined_join_messages_ = "\n".join(self.brawl_info[ctx.guild.id]["join_log"])

        if author_and_guild in self.users[ctx.guild.id]:
            self.users[ctx.guild.id][author_and_guild]["wallet"] -= bet

        with open("Data/economics.json", "w") as economy_file:
            json.dump(self.users[ctx.guild.id], economy_file, indent=4)

        embed = discord.Embed(
            title=self.brawl_info[ctx.guild.id]["scene"],
            description=f"Uh-oh. Someone didn't like someone's face and now a classic brawl is about to break out. "
                        f"Seems like rules won't apply in this match.\n\n**Current brawlers:** {joined_brawlers} "
                        f"[**{len(self.brawl_players[ctx.guild.id])}**]\n**Required bet:** "
                        f"{self.brawl_info[ctx.guild.id]['bet']} ¤\n\n**Join log:**\n{joined_join_messages_}",
            color=discord.Color.dark_green()
        )
        self.messages[ctx.guild.id]["brawl"] = await ctx.respond(embed=embed, view=self.resolve_view(ctx))

    @commands.slash_command(description="Create a game of blackjack")
    @discord.option(name="bet", description="The amount of credits you wish to bet on a game of blackjack",
                    required=False)
    async def blackjack(self, ctx: discord.ApplicationContext, bet: int = 0):
        await ctx.defer()

        with open("Data/economics.json", "r") as economy_file:
            self.users[ctx.guild.id] = json.load(economy_file)

        author_and_guild = f"{ctx.user.id}-{ctx.guild.id}"

        if ctx.user.id in self.blackjack_players[ctx.guild.id]:
            embed = discord.Embed(
                description="**Error:** You have an ongoing game of blackjack.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        elif bet and author_and_guild not in self.users[ctx.guild.id]:
            embed = discord.Embed(
                description="**Note:** Please create an account using the `register` command to place bets.",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return
        elif bet and author_and_guild in self.users[ctx.guild.id] and \
                self.users[ctx.guild.id][author_and_guild]["wallet"] < bet:
            embed = discord.Embed(
                description="**Error:** Your wallet balance is too low to place this bet.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        self.blackjack_bet[ctx.guild.id][ctx.user.id] = bet
        self.deck[ctx.guild.id][ctx.user.id] = await self.create_deck()
        self.blackjack_players[ctx.guild.id][ctx.user.id] = [self.deck[ctx.guild.id][ctx.user.id].pop(0),
                                                             self.deck[ctx.guild.id][ctx.user.id].pop(0)]
        self.blackjack_players[ctx.guild.id][0] = [self.deck[ctx.guild.id][ctx.user.id].pop(0), "?"]

        joined_player_cards = "\n".join(self.blackjack_players[ctx.guild.id][ctx.user.id])
        joined_dealer_cards = "\n".join(self.blackjack_players[ctx.guild.id][0])
        player_total = await self.calculate_total(ctx, ctx.user.id)
        dealer_total = await self.calculate_total(ctx, 0)

        if author_and_guild in self.users[ctx.guild.id]:
            self.users[ctx.guild.id][author_and_guild]["wallet"] -= bet

        with open("Data/economics.json", "w") as economy_file:
            json.dump(self.users[ctx.guild.id], economy_file, indent=4)

        embed = discord.Embed(
            description=f"**Bet: {self.blackjack_bet[ctx.guild.id][ctx.user.id]}** ¤\n\n"
                        f"**Your hand:**\n{joined_player_cards}\n**Total value:** {player_total}\n\n"
                        f"**Dealer's hand:**\n{joined_dealer_cards}\n**Total value:** {dealer_total}",
            color=discord.Color.dark_green()
        )
        self.messages[ctx.guild.id]["blackjack"][ctx.user.id] = await ctx.respond(
            embed=embed, view=self.views[ctx.guild.id]["blackjack"])

        if player_total == 21:
            winnings = self.blackjack_bet[ctx.guild.id][ctx.user.id] * 2

            if author_and_guild in self.users[ctx.guild.id]:
                self.users[ctx.guild.id][author_and_guild]["wallet"] += winnings

                with open("Data/economics.json", "w") as economy_file:
                    json.dump(self.users[ctx.guild.id], economy_file, indent=4)

            embed = discord.Embed(
                description=f"You have won via blackjack. Congratulations, your wallet just got bigger by "
                            f"**{winnings}** ¤.",
                color=discord.Color.dark_gold()
            )
            await ctx.followup.send(embed=embed)
            await self.blackjack_cleanup(ctx, ctx.user.id)

    @blackjack.before_invoke
    @brawl.before_invoke
    async def ensure_dicts(self, ctx: discord.ApplicationContext):
        if ctx.guild.id not in self.brawl_players:
            with open("Data/economics.json", "r") as economy_file:
                self.users[ctx.guild.id] = json.load(economy_file)

            self.messages[ctx.guild.id] = {"blackjack": {}, "brawl": None}
            self.deck[ctx.guild.id] = {}
            self.blackjack_players[ctx.guild.id] = {}
            self.blackjack_bet[ctx.guild.id] = {}
            self.brawl_players[ctx.guild.id] = {}
            self.brawl_info[ctx.guild.id] = {"bet": 0, "scene": None, "join_log": []}
            self.gui[ctx.guild.id] = {
                "blackjack_hit": Button(label="Hit", style=discord.ButtonStyle.secondary),
                "blackjack_stand": Button(label="Stand", style=discord.ButtonStyle.secondary),
                "blackjack_reset": Button(label="Reset", style=discord.ButtonStyle.danger),
                "brawl_begin": Button(style=discord.ButtonStyle.success, label="Begin", row=1),
                "brawl_join": Button(style=discord.ButtonStyle.success, label="Join", row=1),
                "brawl_add": Button(style=discord.ButtonStyle.secondary, label="Add bot", row=2),
                "brawl_remove": Button(style=discord.ButtonStyle.danger, label="Remove bot", row=2),
                "brawl_cancel": Button(style=discord.ButtonStyle.danger, label="Cancel", row=1),
                "brawl_reset": Button(label="Reset", style=discord.ButtonStyle.danger)
            }
            self.views[ctx.guild.id] = {
                "blackjack": View(timeout=None),
                "blackjack_reset": View(timeout=None),
                "brawl_all": View(timeout=None),
                "brawl_no_add": View(timeout=None),
                "brawl_no_remove": View(timeout=None),
                "brawl_reset": View(timeout=None)
            }

            for elem in self.gui[ctx.guild.id].keys():
                self.gui[ctx.guild.id][elem].callback = await self.resolve_gui_callback(ctx, elem)

                for view in self.views[ctx.guild.id].keys():
                    if view.startswith("blackjack"):
                        if not elem.startswith("blackjack") or \
                                (view == "blackjack_reset" and elem != "blackjack_reset") or \
                                (view != "blackjack_reset" and elem == "blackjack_reset"):
                            continue
                    else:
                        if not elem.startswith("brawl") or (view == "brawl_reset" and elem != "brawl_reset") or \
                                (view == "brawl_no_add" and elem == "brawl_add") or \
                                (view == "brawl_no_remove" and elem == "brawl_remove") or \
                                (view != "brawl_reset" and elem == "brawl_reset"):
                            continue
                    self.views[ctx.guild.id][view].add_item(self.gui[ctx.guild.id][elem])


def setup(bot):
    bot.add_cog(Game(bot))
