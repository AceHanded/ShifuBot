import discord
from discord import option
from discord.ui import Button, View
from discord.ext import commands
import random
import asyncio
import json
from Cogs.utils import Constants, get_language_strings


BRAWL = {}
BLACKJACK = {}


class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Create a game of brawl")
    @option(name="bet", description="The amount of credits you wish to bet on a game of brawl", required=False)
    async def brawl(self, ctx, bet: int = 0):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        scenes = strings["Brawl.Scenes"]
        attack_means = strings["Brawl.AttackMeans"]
        attack_spot = strings["Brawl.AttackSpot"]

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return

        begin_button = Button(style=discord.ButtonStyle.success, label="Begin", row=1)
        join_button = Button(style=discord.ButtonStyle.success, label="Join", row=1)
        add_button = Button(style=discord.ButtonStyle.secondary, label="Add bot", row=2)
        remove_button = Button(style=discord.ButtonStyle.danger, label="Remove bot", row=2)
        cancel_button = Button(style=discord.ButtonStyle.danger, label="Cancel", row=1)
        reset_button = Button(label="Reset", style=discord.ButtonStyle.danger)

        async def reset_button_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(view=None)

            try:
                del BRAWL[ctx.guild.id]
            except KeyError:
                pass

        async def begin_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            if len(BRAWL[ctx.guild.id]["Players"]) > 1:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=None)

                actions = [strings["Brawl.LogMessage0"]]
                player_multiplier = len(BRAWL[ctx.guild.id]["Players"])

                embed_ = discord.Embed(
                    title=strings["Brawl.BrawlLog"],
                    description=f"{actions[0]}",
                    color=discord.Color.dark_green(),
                )
                main = await interaction.followup.send(embed=embed_)

                while len(BRAWL[ctx.guild.id]["Players"]) > 1:
                    await asyncio.sleep(1)

                    random_player = random.choice(list(BRAWL[ctx.guild.id]["Players"].keys()))
                    random_dmg = random.randrange(11)
                    BRAWL[ctx.guild.id]["Players"][random_player]["HP"] -= random_dmg
                    filtered = {ctx.guild.id: []}

                    for player in BRAWL[ctx.guild.id]["Players"]:
                        if player != random_player:
                            filtered[ctx.guild.id].append(player)

                    if random_dmg == 0:
                        action_message = strings["Brawl.AttackFailure"].format(
                            random.choice(filtered[ctx.guild.id]), random_player, random.choice(attack_means),
                            random_dmg, BRAWL[ctx.guild.id]["Players"][random_player]["HP"])
                        actions.append(f"[**{len(actions) + 1}**] {action_message}")
                    elif 0 < random_dmg < 10:
                        action_message = strings["Brawl.AttackSuccess"].format(
                            random.choice(filtered[ctx.guild.id]), random_dmg, random_player,
                            random.choice(attack_means), BRAWL[ctx.guild.id]["Players"][random_player]["HP"])
                        actions.append(f"[**{len(actions) + 1}**] {action_message}")
                    else:
                        action_message = strings["Brawl.AttackCritical"].format(
                            random.choice(filtered[ctx.guild.id]), random_dmg, random_player,
                            random.choice(attack_means), BRAWL[ctx.guild.id]["Players"][random_player]["HP"],
                            random.choice(attack_spot))
                        actions.append(f"[**{len(actions) + 1}**] {action_message}")

                    if BRAWL[ctx.guild.id]["Players"][random_player]["HP"] <= 0:
                        BRAWL[ctx.guild.id]["Fallen"] = True
                        actions.append(strings["Brawl.Fallen"].format(len(actions) + 1, random_player))
                        BRAWL[ctx.guild.id]["Players"].pop(random_player)

                    joined_actions = "\n".join(actions)
                    color_choice = discord.Color.dark_red() if BRAWL[ctx.guild.id]["Fallen"] else \
                        discord.Color.dark_blue() if random_dmg == 0 else \
                        discord.Color.purple() if random_dmg == 10 else discord.Color.dark_green()
                    BRAWL[ctx.guild.id]["Fallen"] = False

                    embed_ = discord.Embed(
                        title=strings["Brawl.BrawlLog"],
                        description=f"{joined_actions}",
                        color=color_choice
                    )
                    await main.edit(embed=embed_)

                winner_id = BRAWL[ctx.guild.id]["Players"][list(BRAWL[ctx.guild.id]["Players"].keys())[0]]["ID"]
                winner_and_guild = f"{winner_id}-{ctx.guild.id}"

                if winner_and_guild in users:
                    winnings = random.randrange(10, 25) + (BRAWL[ctx.guild.id]["Bet"] * player_multiplier)
                    users[winner_and_guild]["Wallet"] += int(winnings)

                    with open("Data/economics.json", "w") as economy_file_:
                        json.dump(users, economy_file_, indent=4)

                    embed_ = discord.Embed(
                        description=strings["Brawl.Victory"].format(
                            list(BRAWL[ctx.guild.id]["Players"].keys())[0], BRAWL[ctx.guild.id]["Scene"], winnings),
                        color=discord.Color.dark_gold(),
                    )
                    await interaction.followup.send(embed=embed_)
                else:
                    embed_ = discord.Embed(
                        description=strings["Brawl.VictoryNoAccount"].format(
                            list(BRAWL[ctx.guild.id]["Players"].keys())[0], BRAWL[ctx.guild.id]["Scene"]),
                        color=discord.Color.dark_gold(),
                    )
                    await interaction.followup.send(embed=embed_)

                BRAWL[ctx.guild.id]["Players"].clear()
                del BRAWL[ctx.guild.id]
            else:
                embed_ = discord.Embed(
                    description=strings["Errors.InsufficientBrawlers"],
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed_, ephemeral=True)
                return

        async def join_button_callback(interaction: discord.Interaction):
            author_and_guild_ = f"{interaction.user.id}-{ctx.guild.id}"

            if bet and bet > users[author_and_guild_]["Wallet"]:
                embed_ = discord.Embed(
                    description=strings["Errors.BrawlCannotAffordInitialize"],
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed_, ephemeral=True)
                return

            if interaction.user.name in BRAWL[ctx.guild.id]["Players"]:
                embed_ = discord.Embed(
                    description=strings["Errors.BrawlAlreadyReady"],
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed_, ephemeral=True)
                return
            else:
                BRAWL[ctx.guild.id]["Players"][interaction.user.name] = {"HP": 20, "ID": interaction.user.id}

                users[author_and_guild]["Wallet"] -= BRAWL[ctx.guild.id]["Bet"]

                with open("Data/economics.json", "w") as economy_file_:
                    json.dump(users, economy_file_, indent=4)

                BRAWL[ctx.guild.id]["JoinMessages"].append(strings["Brawl.Joined"].format(interaction.user.name))
                joined_join_messages_ = "\n".join(BRAWL[ctx.guild.id]["JoinMessages"])

                embed_ = discord.Embed(
                    title=BRAWL[ctx.guild.id]["Scene"],
                    description=strings["Brawl.Desc"].format(
                        ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"]),
                        BRAWL[ctx.guild.id]["Bet"], joined_join_messages_),
                    color=discord.Color.dark_green(),
                )
                await BRAWL[ctx.guild.id]["Msg"].edit(embed=embed_)

        async def cancel_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            if interaction.user.name not in BRAWL[ctx.guild.id]["Players"]:
                embed_ = discord.Embed(
                    description=strings["Errors.BrawlNotPartaking"],
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed_)
                return

            author_and_guild_ = f"{interaction.user.id}-{ctx.guild.id}"

            BRAWL[ctx.guild.id]["Players"].pop(interaction.user.name)
            users[author_and_guild_]["Wallet"] += BRAWL[ctx.guild.id]["Bet"]

            with open("Data/economics.json", "w") as economy_file_:
                json.dump(users, economy_file_, indent=4)

            if all(player["ID"] == 000000000000000000 for player in BRAWL[ctx.guild.id]["Players"].values()):
                BRAWL[ctx.guild.id]["Players"].clear()

            BRAWL[ctx.guild.id]["JoinMessages"].append(strings["Brawl.Left"].format(interaction.user.name))
            joined_join_messages_ = "\n".join(BRAWL[ctx.guild.id]["JoinMessages"])
            brawlers_and_bet = strings["Brawl.BrawlersAndBet"].format(
                ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"]),
                BRAWL[ctx.guild.id]["Bet"])

            embed_ = discord.Embed(
                title=BRAWL[ctx.guild.id]["Scene"],
                description=strings["Brawl.DescNoBrawlers"].format(
                    brawlers_and_bet if BRAWL[ctx.guild.id]["Players"] else strings["Brawl.Cancelled"],
                    joined_join_messages_),
                color=discord.Color.dark_red(),
            )
            await BRAWL[ctx.guild.id]["Msg"].edit(embed=embed_)

            if not BRAWL[ctx.guild.id]["Players"]:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=None)
                del BRAWL[ctx.guild.id]

        async def add_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            first_names, second_names = strings["Brawl.namelist0"], strings["Brawl.namelist1"]

            random_name = f"{random.choice(first_names)} {random.choice(second_names)}"
            BRAWL[ctx.guild.id]["Players"][random_name] = {"HP": 20, "ID": 000000000000000000}

            BRAWL[ctx.guild.id]["JoinMessages"].append(strings["Brawl.Joined"].format(random_name))
            joined_join_messages_ = "\n".join(BRAWL[ctx.guild.id]["JoinMessages"])

            embed_ = discord.Embed(
                title=BRAWL[ctx.guild.id]["Scene"],
                description=strings["Brawl.Desc"].format(
                    ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"]),
                    BRAWL[ctx.guild.id]["Bet"], joined_join_messages_),
                color=discord.Color.dark_green(),
            )
            await BRAWL[ctx.guild.id]["Msg"].edit(embed=embed_)

            if sum(1 for player in BRAWL[ctx.guild.id]["Players"].values() if player["ID"] == 000000000000000000) == 3:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=view3)
            else:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=view)

        async def remove_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            bot = next((k, v) for k, v in BRAWL[ctx.guild.id]["Players"].items() if v["ID"] == 000000000000000000)
            BRAWL[ctx.guild.id]["Players"].pop(bot[0])

            BRAWL[ctx.guild.id]["JoinMessages"].append(strings["Brawl.Removed"].format(bot[0]))
            joined_join_messages_ = "\n".join(BRAWL[ctx.guild.id]["JoinMessages"])

            embed_ = discord.Embed(
                title=BRAWL[ctx.guild.id]["Scene"],
                description=strings["Brawl.Desc"].format(
                    ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"]),
                    BRAWL[ctx.guild.id]["Bet"], joined_join_messages_),
                color=discord.Color.dark_red(),
            )
            await BRAWL[ctx.guild.id]["Msg"].edit(embed=embed_)

            if not BRAWL[ctx.guild.id]["Players"]:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=None)
                del BRAWL[ctx.guild.id]
            elif not (any(player["ID"] == 000000000000000000 for player in BRAWL[ctx.guild.id]["Players"].values())):
                await BRAWL[ctx.guild.id]["Msg"].edit(view=view2)
            else:
                await BRAWL[ctx.guild.id]["Msg"].edit(view=view)

        button_callbacks = {begin_button: begin_button_callback, join_button: join_button_callback,
                            add_button: add_button_callback, cancel_button: cancel_button_callback,
                            remove_button: remove_button_callback, reset_button: reset_button_callback}

        for button, callback in button_callbacks.items():
            button.callback = callback

        view = View(timeout=None)
        view2 = View(timeout=None)
        view3 = View(timeout=None)
        view4 = View(timeout=None)

        for view_ in [view, view2, view3, view4]:
            view_.add_item(begin_button), view_.add_item(join_button), view_.add_item(cancel_button) if view_ != view4 \
                else view_.add_item(reset_button)
            view_.add_item(add_button) if view_ == view or view_ == view2 else None
            view_.add_item(remove_button) if view_ == view or view_ == view3 else None

        if not BRAWL[ctx.guild.id]["State"]:
            if bet and bet > users[author_and_guild]["Wallet"]:
                embed = discord.Embed(
                    description=strings["Errors.BrawlCannotAffordInitialize"],
                    color=discord.Color.red(),
                )
                await ctx.respond(embed=embed)
                return

            BRAWL[ctx.guild.id]["Players"] = {ctx.author.name: {"HP": 20, "ID": ctx.author.id}}
            BRAWL[ctx.guild.id]["State"] = True
            BRAWL[ctx.guild.id]["Bet"] = bet
            BRAWL[ctx.guild.id]["Scene"] = random.choice(scenes)
            users[author_and_guild]["Wallet"] -= bet

            with open("Data/economics.json", "w") as economy_file:
                json.dump(users, economy_file, indent=4)

            joined_join_messages = "\n".join(BRAWL[ctx.guild.id]["JoinMessages"])

            embed = discord.Embed(
                title=f"{BRAWL[ctx.guild.id]['Scene']}",
                description=strings["Brawl.Desc"].format(
                    ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"]),
                    BRAWL[ctx.guild.id]["Bet"], joined_join_messages),
                color=discord.Color.dark_green(),
            )
            BRAWL[ctx.guild.id]["Msg"] = await ctx.followup.send(embed=embed, view=view2)
        else:
            if ctx.author.name in BRAWL[ctx.guild.id]["Players"]:
                embed = discord.Embed(
                    description=strings["Errors.BrawlAlreadyReady"],
                    color=discord.Color.red(),
                )
                await ctx.respond(embed=embed, view=view4)
                return

            if bet and bet > users[author_and_guild]["Wallet"]:
                embed = discord.Embed(
                    description=strings["Errors.BrawlCannotAffordJoin"],
                    color=discord.Color.red(),
                )
                await ctx.respond(embed=embed)
                return

            BRAWL[ctx.guild.id]["Players"][ctx.author.name] = {"HP": 20, "ID": ctx.author.id}
            users[author_and_guild]["Wallet"] -= BRAWL[ctx.guild.id]["Bet"]

            with open("Data/economics.json", "w") as economy_file:
                json.dump(users, economy_file, indent=4)

            embed = discord.Embed(
                description=strings["Brawl.JoinedAndBrawlers"].format(
                    ctx.author.name, ", ".join(BRAWL[ctx.guild.id]["Players"]), len(BRAWL[ctx.guild.id]["Players"])),
                color=discord.Color.dark_green(),
            )
            await ctx.respond(embed=embed)

    @commands.slash_command(description="Create a game of blackjack")
    @option(name="bet", description="The amount of credits you wish to bet on a game of blackjack", required=False)
    async def blackjack(self, ctx, bet: int = 0):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        with open("Data/economics.json", "r") as f:
            users = json.load(f)

        if author_and_guild not in users:
            embed = discord.Embed(
                description=strings["Notes.CreateAccount"],
                color=discord.Color.blue(),
            )
            await ctx.followup.send(embed=embed)
            return

        hit_button = Button(label="Hit", style=discord.ButtonStyle.secondary)
        stand_button = Button(label="Stand", style=discord.ButtonStyle.secondary)
        reset_button = Button(label="Reset", style=discord.ButtonStyle.danger)

        async def reset_button_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(view=None)

            try:
                del BLACKJACK[ctx.guild.id][ctx.author.id]
            except KeyError:
                pass

        async def hit_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            added_player_value_ = random.choice(Constants.CARD_VALUE)
            added_player_suit_ = random.choice(list(Constants.CARD_SUIT.keys()))
            added_player_card_ = f"{added_player_value_} of {added_player_suit_}"

            BLACKJACK[ctx.guild.id][ctx.author.id]["Player"].append(f"{added_player_card_} "
                                                                    f"{Constants.CARD_SUIT[added_player_suit_]}")

            BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerJoined"] = \
                "\n".join(BLACKJACK[ctx.guild.id][ctx.author.id]["Player"])

            for value_ in BLACKJACK[ctx.guild.id][ctx.author.id]["Player"]:
                if value_ in ("Ace of Hearts", "Ace of Diamonds", "Ace of Spades", "Ace of Clubs"):
                    BLACKJACK[ctx.guild.id][ctx.author.id]["Player"]. \
                        pop(BLACKJACK[ctx.guild.id][ctx.author.id]["Player"].index(value_))
                    BLACKJACK[ctx.guild.id][ctx.author.id]["Player"].insert(-1, value_)

            BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] = 0
            for value_ in BLACKJACK[ctx.guild.id][ctx.author.id]["Player"]:
                value_ = value_.split(" of ")[0]

                if value_ in ("Jack", "Queen", "King"):
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 10
                elif value_ == "Ace":
                    if BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] + 11 > 21:
                        BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 1
                    else:
                        BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 11
                else:
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += int(value_)

            embed_ = discord.Embed(
                description=strings["Blackjack.Main"].format(
                    BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"],
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerJoined"],
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"],
                    BLACKJACK[ctx.guild.id][ctx.author.id]["DealerJoined"],
                    BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"]),
                color=discord.Color.dark_green()
            )
            await interaction.followup.edit_message(message_id=BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].id,
                                                    embed=embed_)

            if BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] == 21:
                try:
                    await BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].edit(view=None)
                except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
                    pass

                embed_ = discord.Embed(
                    description=strings["Blackjack.VictoryBlackjack"].format(
                        int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)),
                    color=discord.Color.dark_gold()
                )
                await ctx.send(embed=embed_)

                users[author_and_guild]["Wallet"] += int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)

                with open("Data/economics.json", "w") as economy_file_:
                    json.dump(users, economy_file_, indent=4)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]
            elif BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] > 21:
                try:
                    await BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].edit(view=None)
                except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
                    pass

                embed_ = discord.Embed(
                    description=strings["Blackjack.DefeatOverdraw"].format(
                        BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"]),
                    color=discord.Color.dark_red()
                )
                await ctx.send(embed=embed_)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]

        async def stand_button_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            if not BLACKJACK[ctx.guild.id][ctx.author.id]["State"]:
                return

            try:
                await interaction.followup.edit_message(message_id=BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].id,
                                                        view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
                pass

            BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].pop(-1)

            while BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] < \
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"]:
                await asyncio.sleep(1)

                added_dealer_value_ = random.choice(Constants.CARD_VALUE)
                added_dealer_suit_ = random.choice(list(Constants.CARD_SUIT.keys()))
                added_dealer_card_ = f"{added_dealer_value_} of {added_dealer_suit_}"

                BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].append(f"{added_dealer_card_} "
                                                                        f"{Constants.CARD_SUIT[added_dealer_suit_]}")

                BLACKJACK[ctx.guild.id][ctx.author.id]["DealerJoined"] = \
                    "\n".join(BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"])

                for value_ in BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"]:
                    if value_ in ("Ace of Hearts", "Ace of Diamonds", "Ace of Spades", "Ace of Clubs"):
                        BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"]. \
                            pop(BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].index(value_))
                        BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].insert(-1, value_)

                BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] = 0
                for value_ in BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"]:
                    value_ = value_.split(" of ")[0]

                    if value_ in ("Jack", "Queen", "King"):
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 10
                    elif value_ == "Ace":
                        if BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] + 11 > 21:
                            BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 1
                        else:
                            BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 11
                    else:
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += int(value_)

                embed_ = discord.Embed(
                    description=strings["Blackjack.Main"].format(
                        BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"],
                        BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerJoined"],
                        BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"],
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerJoined"],
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"]),
                    color=discord.Color.dark_green()
                )
                await BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].edit(embed=embed_)

            if BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] == 21:
                embed_ = discord.Embed(
                    description=strings["Blackjack.DefeatBlackjack"].format(
                        BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"]),
                    color=discord.Color.dark_red()
                )
                await ctx.send(embed=embed_)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]
            elif BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] > 21:
                embed_ = discord.Embed(
                    description=strings["Blackjack.VictoryOverdraw"].format(
                        int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)),
                    color=discord.Color.dark_gold()
                )
                await ctx.send(embed=embed_)

                users[author_and_guild]["Wallet"] += int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)

                with open("Data/economics.json", "w") as economy_file_:
                    json.dump(users, economy_file_, indent=4)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]
            elif BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] == \
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"]:
                embed_ = discord.Embed(
                    description=strings["Blackjack.Tie"].format(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"]),
                    color=discord.Color.dark_blue()
                )
                await ctx.send(embed=embed_)

                users[author_and_guild]["Wallet"] += BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"]

                with open("Data/economics.json", "w") as economy_file_:
                    json.dump(users, economy_file_, indent=4)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]
            else:
                embed_ = discord.Embed(
                    description=strings["Blackjack.DefeatHigher"].format(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"]),
                    color=discord.Color.dark_red()
                )
                await ctx.send(embed=embed_)

                del BLACKJACK[ctx.guild.id][ctx.author.id]

                if len(BLACKJACK[ctx.guild.id]) == 0:
                    del BLACKJACK[ctx.guild.id]

        hit_button.callback, stand_button.callback = hit_button_callback, stand_button_callback
        reset_button.callback = reset_button_callback

        view = View(timeout=None)
        view2 = View(timeout=None)
        view.add_item(hit_button), view.add_item(stand_button)
        view2.add_item(reset_button)

        if BLACKJACK[ctx.guild.id] and BLACKJACK[ctx.guild.id][ctx.author.id]["State"]:
            embed = discord.Embed(
                description=strings["Errors.BlackjackAlreadyActive"],
                color=discord.Color.red(),
            )
            BLACKJACK[ctx.guild.id][ctx.author.id]["ErrorMsg"] = await ctx.followup.send(embed=embed, view=view2)
            return

        if bet > users[author_and_guild]["Wallet"]:
            embed = discord.Embed(
                description=strings["Errors.BlackjackCannotAffordBet"],
                color=discord.Color.red(),
            )
            await ctx.followup.send(embed=embed)
            return

        BLACKJACK[ctx.guild.id][ctx.author.id]["State"] = True
        BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] = bet

        users[author_and_guild]["Wallet"] -= bet

        with open("Data/economics.json", "w") as economy_file:
            json.dump(users, economy_file, indent=4)

        for _ in range(0, 2):
            added_player_value = random.choice(Constants.CARD_VALUE)
            added_player_suit = random.choice(list(Constants.CARD_SUIT.keys()))
            added_player_card = f"{added_player_value} of {added_player_suit}"

            BLACKJACK[ctx.guild.id][ctx.author.id]["Player"].append(f"{added_player_card} "
                                                                    f"{Constants.CARD_SUIT[added_player_suit]}")

        added_dealer_value = random.choice(Constants.CARD_VALUE)
        added_dealer_suit = random.choice(list(Constants.CARD_SUIT.keys()))
        added_dealer_card = f"{added_dealer_value} of {added_dealer_suit}"

        BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].append(f"{added_dealer_card} "
                                                                f"{Constants.CARD_SUIT[added_dealer_suit]}")
        BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"].append("?")

        BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerJoined"] = \
            "\n".join(BLACKJACK[ctx.guild.id][ctx.author.id]["Player"])
        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerJoined"] = \
            "\n".join(BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"])

        for value in BLACKJACK[ctx.guild.id][ctx.author.id]["Player"]:
            value = value.split(" of ")[0]

            if value in ("Jack", "Queen", "King"):
                BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 10
            elif value == "Ace":
                if BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] + 11 > 21:
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 1
                else:
                    BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += 11
            else:
                BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] += int(value)

        for value in BLACKJACK[ctx.guild.id][ctx.author.id]["Dealer"]:
            if value != "?":
                value = value.split(" of ")[0]

                if value in ("Jack", "Queen", "King"):
                    BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 10
                elif value == "Ace":
                    if BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] + 11 > 21:
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 1
                    else:
                        BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += 11
                else:
                    BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"] += int(value)

        embed = discord.Embed(
            description=strings["Blackjack.Main"].format(
                BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"],
                BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerJoined"],
                BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"],
                BLACKJACK[ctx.guild.id][ctx.author.id]["DealerJoined"],
                BLACKJACK[ctx.guild.id][ctx.author.id]["DealerValue"]),
            color=discord.Color.dark_green(),
        )
        BLACKJACK[ctx.guild.id][ctx.author.id]["Main"] = await ctx.followup.send(embed=embed, view=view)

        if BLACKJACK[ctx.guild.id][ctx.author.id]["PlayerValue"] == 21:
            try:
                await BLACKJACK[ctx.guild.id][ctx.author.id]["Main"].edit(view=None)
            except (discord.NotFound, discord.HTTPException, AttributeError, KeyError, UnboundLocalError):
                pass

            embed = discord.Embed(
                description=strings["Blackjack.VictoryBlackjack"].format(
                    int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)),
                color=discord.Color.dark_gold()
            )
            await ctx.send(embed=embed)

            users[author_and_guild]["Wallet"] += int(BLACKJACK[ctx.guild.id][ctx.author.id]["Bet"] * 2.0)

            with open("Data/economics.json", "w") as economy_file:
                json.dump(users, economy_file, indent=4)

            del BLACKJACK[ctx.guild.id][ctx.author.id]

            if not BLACKJACK[ctx.guild.id]:
                del BLACKJACK[ctx.guild.id]

    @brawl.before_invoke
    async def ensure_brawl(self, ctx):
        if ctx.guild.id not in BRAWL:
            BRAWL[ctx.guild.id] = {"State": False, "Bet": 0, "Players": {}, "Msg": None, "JoinMessages": [],
                                   "Fallen": False}

    @blackjack.before_invoke
    async def ensure_blackjack(self, ctx):
        if ctx.guild.id not in BLACKJACK:
            BLACKJACK[ctx.guild.id] = {}
        if ctx.author.id not in BLACKJACK[ctx.guild.id]:
            BLACKJACK[ctx.guild.id][ctx.author.id] = {"State": False, "Bet": 0, "Player": [], "Dealer": [],
                                                      "PlayerJoined": "", "DealerJoined": "", "PlayerValue": 0,
                                                      "DealerValue": 0, "Main": None, "ErrorMsg": None}


def setup(bot):
    bot.add_cog(Game(bot))
