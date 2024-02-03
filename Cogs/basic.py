import discord
from discord import option
from discord.ext import commands
import asyncio
import random
import json
import openai
from dotenv import load_dotenv
import os
from Cogs.utils import Constants, get_language_strings


load_dotenv()

COOLDOWN = {}

openai.api_key = os.getenv("OPENAI_API_KEY")


class Basic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(description="Generate text or images using OpenAI")
    @option(name="type_", description="Whether you want to generate text or an image", choices=["Text", "Image"],
            required=True)
    @option(name="prompt", description="The prompt from which you wish something to be generated", required=True)
    @option(name="temperature", description="The creativity percentage of the answer (50 by default)", required=False)
    @option(name="image_scale", description="The resolution of the image (1024x1024 by default)",
            choices=["1024x1024", "512x512", "256x256"], required=False)
    @option(name="engine", description="The model engine which generates the answer (gpt-3.5-turbo by default)",
            choices=["gpt-3.5-turbo", "text-davinci-003", "text-curie-001", "text-babbage-001", "text-ada-001"],
            required=False)
    async def generate(self, ctx, type_: str, prompt: str, temperature: int = 50, image_scale: str = "1024x1024",
                       engine: str = "gpt-3.5-turbo"):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        temperature = min(max(temperature, 0), 100) / 100

        embed = discord.Embed(
            description=strings["Generate.Prompt"].format(prompt),
            color=discord.Color.dark_green(),
        )
        main = await ctx.followup.send(embed=embed)

        try:
            if type_ == "Text":
                if engine == "gpt-3.5-turbo":
                    output = openai.ChatCompletion.create(model=engine, messages=[{"role": "user", "content": prompt}],
                                                          temperature=temperature, max_tokens=512)
                    text = output["choices"][0]["message"]["content"]
                else:
                    output = openai.Completion.create(engine=engine, prompt=prompt, temperature=temperature,
                                                      max_tokens=512)
                    text = output["choices"][0]["text"]

                await ctx.send(f"```{text}```")

                embed = discord.Embed(
                    description=strings["Generate.SuccessText"].format(prompt),
                    color=discord.Color.dark_green(),
                )
            else:
                output = openai.Image.create(prompt=prompt, n=1, size=image_scale)

                await ctx.send(output["data"][0]["url"])

                embed = discord.Embed(
                    description=strings["Generate.SuccessImage"].format(prompt),
                    color=discord.Color.dark_green(),
                )
        except openai.InvalidRequestError as e:
            print(e)
            embed = discord.Embed(
                description=strings["Errors.InvalidRequest"],
                color=discord.Color.red(),
            )
        except openai.error.RateLimitError:
            embed = discord.Embed(
                description=strings["Errors.QuotaExceeded"],
                color=discord.Color.red(),
            )
        await main.edit(embed=embed)

    @commands.slash_command(description="Fifty-two in the deck, guess the suit for a chance to win credits")
    @option(name="guess", description="Guess the card suit", choices=["Hearts", "Diamonds", "Spades", "Clubs"],
            required=False)
    async def card(self, ctx, guess: str = None):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        with open("Data/economics.json", "r") as economy_file:
            users = json.load(economy_file)

        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        random_value = random.choice(Constants.CARD_VALUE)
        random_suit = random.choice(list(Constants.CARD_SUIT.keys()))

        card = f"{random_value} of {random_suit}"

        if not guess:
            embed = discord.Embed(
                title=f"{random_suit} {Constants.CARD_SUIT[random_suit]}",
                description=f"{card}",
                color=discord.Color.dark_red() if random_suit in ("Diamonds", "Hearts") else discord.Color.darker_gray()
            )
            await ctx.followup.send(embed=embed)
        else:
            if not COOLDOWN[author_and_guild][1] == 0:
                embed = discord.Embed(
                    description=strings["Errors.CooldownCard"].format(120 - COOLDOWN[author_and_guild]),
                    color=discord.Color.red(),
                )
                await ctx.followup.send(embed=embed)
                return
            elif author_and_guild not in users:
                embed = discord.Embed(
                    description=strings["Notes.CreateAccount"],
                    color=discord.Color.blue(),
                )
                await ctx.respond(embed=embed)
                return

            win_amount = random.randrange(10, 25)

            if random_suit == guess:
                embed = discord.Embed(
                    title=f"{random_suit} {Constants.CARD_SUIT[random_suit]}",
                    description=strings["Basic.GuessCorrect"].format(card, win_amount),
                    color=discord.Color.dark_red() if random_suit in ("Diamonds", "Hearts") else
                    discord.Color.darker_gray()
                )
                await ctx.followup.send(embed=embed)

                users[author_and_guild]["Wallet"] += win_amount

                with open("Data/economics.json", "w") as economy_file:
                    json.dump(users, economy_file, indent=4)
            else:
                embed = discord.Embed(
                    title=f"{random_suit} {Constants.CARD_SUIT[random_suit]}",
                    description=strings["Basic.GuessIncorrect"].format(card),
                    color=discord.Color.dark_red() if random_suit in ("Diamonds", "Hearts") else
                    discord.Color.darker_gray()
                )
                await ctx.followup.send(embed=embed)

            while COOLDOWN[author_and_guild] != 120:
                await asyncio.sleep(1)
                COOLDOWN[author_and_guild] += 1
                continue

            if COOLDOWN[author_and_guild] == 120:
                COOLDOWN[author_and_guild] = 0

    @commands.slash_command(description="Heads or tails?")
    @option(name="count", description="How many times the coin is flipped", required=False)
    async def coin(self, ctx, count: int = 1):
        await ctx.defer()

        strings = await get_language_strings(ctx)

        flips, tails_count = [], 0

        for index in range(min(max(int(count), 1), 10)):
            if random.randint(0, 1):
                flips.append(strings["Basic.Tails"].format(index + 1))
                tails_count += 1
            else:
                flips.append(strings["Basic.Heads"].format(index + 1))

        joined_flips = "\n".join(flips)

        embed = discord.Embed(
            description=strings["Basic.CoinToss"].format(
                joined_flips, tails_count, (tails_count / count) * 100, len(flips) - tails_count,
                ((len(flips) - tails_count) / count) * 100),
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Simple help command")
    @option(name="subsection", description="The subsection of the help command",
            choices=["Basic", "Music", "Admin", "Game", "Economy"], required=False)
    async def help(self, ctx, subsection: str = None):
        strings = await get_language_strings(ctx)

        if subsection == "Basic":
            embed = discord.Embed(
                title=strings["Help.Basic"],
                description=strings["Help.BasicDesc"],
                color=discord.Color.dark_gold()
            )
        elif subsection == "Music":
            embed = discord.Embed(
                title=strings["Help.Music"],
                description=strings["Help.MusicDesc"],
                color=discord.Color.dark_gold()
            )
        elif subsection == "Admin":
            embed = discord.Embed(
                title=strings["Help.Admin"],
                description=strings["Help.AdminDesc"],
                color=discord.Color.dark_gold()
            )
        elif subsection == "Game":
            embed = discord.Embed(
                title=strings["Help.Game"],
                description=strings["Help.GameDesc"],
                color=discord.Color.dark_gold()
            )
        elif subsection == "Economy":
            embed = discord.Embed(
                title=strings["Help.Economy"],
                description=strings["Help.EconomyDesc"],
                color=discord.Color.dark_gold()
            )
        else:
            embed = discord.Embed(
                description=strings["Help.GeneralDesc"],
                color=discord.Color.dark_gold()
            )
        try:
            embed.set_author(name=strings["Help.General"].format(ctx.guild.name), icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=strings["Help.General"].format(ctx.guild.name))
        await ctx.response.send_message(embed=embed)

    @commands.slash_command(description="Information about the guild, user and commands")
    @option(name="user", description="The user to get information of", required=False)
    async def information(self, ctx, user: discord.Member = None):
        strings = await get_language_strings(ctx)

        first_part = random.choice(strings["Information.NickList0"])
        second_part = random.choice(strings["Information.NickList1"])
        nickname = f"{first_part}-{second_part}" if first_part[-1] == second_part[0] else f"{first_part}{second_part}"

        rolelist = reversed([role.mention for role in (ctx.author.roles if not user else user.roles)
                             if role != ctx.guild.default_role])
        roles = "\n".join(rolelist)

        embed = discord.Embed(
            description=strings["Information.Desc"].format(
                ctx.guild.name, ctx.guild.id, ctx.guild.member_count, str(ctx.guild.created_at).split('.')[0],
                ctx.author.name if not user else user.name, nickname, ctx.author.id if not user else user.id, roles),
            color=discord.Color.dark_gold()
        )
        try:
            embed.set_author(name=strings["Information.Title"], icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=strings["Information.Title"])
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Awakening thoughts")
    async def thought(self, ctx):
        strings = await get_language_strings(ctx)
        await ctx.response.send_message(random.choice(strings["Basic.Thought"]), tts=True)

    @card.before_invoke
    async def ensure_cooldown(self, ctx):
        author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

        if author_and_guild not in COOLDOWN:
            COOLDOWN[author_and_guild] = 0


def setup(bot):
    bot.add_cog(Basic(bot))
