import discord
from discord import option
from discord.ext import commands
import random
import json
import openai
from dotenv import load_dotenv
import os
from Cogs.utils import Constants


load_dotenv()

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

        temperature = min(max(temperature, 0), 100) / 100

        embed = discord.Embed(
            description=f"Generating an answer from the prompt:\n"
                        f"`{prompt}`\n"
                        f"This will take **a moment**...",
            color=discord.Color.dark_green(),
        )
        main = await ctx.followup.send(embed=embed)

        try:
            if type_ == "Text":
                if engine == "gpt-3.5-turbo":
                    output = openai.ChatCompletion.create(model=engine, messages=[{'role': 'user', 'content': prompt}],
                                                          temperature=temperature, max_tokens=512)
                    text = output["choices"][0]["message"]["content"]
                else:
                    output = openai.Completion.create(engine=engine, prompt=prompt, temperature=temperature,
                                                      max_tokens=512)
                    text = output["choices"][0]["text"]

                await ctx.send(f"```{text}```")

                embed = discord.Embed(
                    description=f"Successfully generated an answer from the prompt:\n"
                                f"`{prompt}`",
                    color=discord.Color.dark_green(),
                )
            else:
                output = openai.Image.create(prompt=prompt, n=1, size=image_scale)

                await ctx.send(output["data"][0]["url"])

                embed = discord.Embed(
                    description=f"Successfully generated an image from the prompt:\n"
                                f"`{prompt}`",
                    color=discord.Color.dark_green(),
                )
        except openai.InvalidRequestError as e:
            print(e)
            embed = discord.Embed(
                description=f"**Error:** Invalid request, please try again later.",
                color=discord.Color.red(),
            )
        await main.edit(embed=embed)

    @commands.slash_command(description="Fifty-two in the deck, guess the suit for a chance to win credits")
    @option(name="guess", description="Guess the card suit", choices=["Hearts", "Diamonds", "Spades", "Clubs"],
            required=False)
    async def card(self, ctx, guess: str = None):
        await ctx.defer()

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
            if author_and_guild not in users:
                embed = discord.Embed(
                    description=f"**Note:** Please create an account first using the `register` command.",
                    color=discord.Color.blue(),
                )
                await ctx.respond(embed=embed)
                return

            win_amount = random.randrange(10, 25)

            if random_suit == guess:
                embed = discord.Embed(
                    title=f"{random_suit} {Constants.CARD_SUIT[random_suit]}",
                    description=f"{card}\n"
                    "**✓** Your guess was **correct**. Congratulations.\n"
                    f"You have won **{win_amount} ¤**",
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
                    description=f"{card}\n"
                    "**✗** Your guess was **incorrect**. Not surprising.",
                    color=discord.Color.dark_red() if random_suit in ("Diamonds", "Hearts") else
                          discord.Color.darker_gray()
                )
                await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Heads or tails?")
    @option(name="count", description="How many times the coin is flipped", required=False)
    async def coin(self, ctx, count: int = 1):
        await ctx.defer()

        flips, tails_count = [], 0

        for index in range(min(max(int(count), 1), 10)):
            if random.randint(0, 1):
                flips.append(f"[**{index + 1}**] \🪙 - Tails")
                tails_count += 1
            else:
                flips.append(f"[**{index + 1}**] \👑 - Heads")

        joined_flips = "\n".join(flips)

        embed = discord.Embed(
            description=f"**Coin toss:**\n"
                        f"{joined_flips}\n\n"
                        f"**In total:** **{tails_count}** Tails [**{(tails_count / count) * 100:.1f} %**] | "
                        f"**{len(flips) - tails_count}** Heads [**{((len(flips) - tails_count) / count)*100:.1f} %**]",
            color=discord.Color.dark_green(),
        )
        await ctx.followup.send(embed=embed)

    @commands.slash_command(description="Simple help command", pass_context=True)
    @option(name="subsection", description="The subsection of the help command",
            choices=["Basic", "Music", "Admin", "Game", "Economy"], required=False)
    async def help(self, ctx, subsection: str = None):
        if subsection == "Basic":
            embed = discord.Embed(
                title="__BASIC COMMANDS__",
                description="**/help {subsection}** - Simple help command\n"
                            "\* **subsection** - The subsection of the help command\n\n"
                            "**/information {user}** - Information about the guild, user and commands\n"
                            "\* **user** - The user to get information of\n\n"
                            "**/thought** - Awakening thoughts\n\n"
                            "**/card {suit}** - Draw a card, guess the suit to win credits\n"
                            "\* **suit** - Guess the card suit\n\n"
                            "**/coin {count}** - Heads or tails?\n"
                            "\* **count** - How many times the coin is flipped\n\n"
                            "**/generate [type_] [prompt] {temperature} {image_scale} {engine}** - Generate text or "
                            "images using OpenAI\n"
                            "\* **type_** - Whether you want to generate text or an image\n"
                            "\* **prompt** - The prompt from which you wish something to be generated\n"
                            "\* **temperature** - The creativity percentage (50 by default)\n"
                            "\* **image_scale** - The resolution of the image (1024x1024 by default)\n"
                            "\* **engine** - The model engine which generates the answer (gpt-3.5-turbo by default)\n\n"
                            "**/perfstat** - Displays performance statistics",
                color=discord.Color.dark_gold()
            )
        elif subsection == "Music":
            embed = discord.Embed(
                title="__MUSIC COMMANDS__",
                description="**/connect** - Invites the bot to the voice channel\n\n"
                            "**/disconnect {after_song}** - Removes the bot from the voice channel and clears the queue\n"
                            "\* **after_song** - Disconnects once current song has ended\n\n"
                            "**/play [query] {insert} {pre_shuffle} {ignore_live} {start_at}** - Adds and plays songs in "
                            "the queue\n"
                            "\* **query** - The song that you want to play (SoundCloud/Spotify/YouTube URL, or query)\n"
                            "\* **insert** - Add the song to the given position in queue\n"
                            "\* **pre_shuffle** - Shuffle the songs of the playlist ahead of time\n"
                            "\* **ignore_live** - Attempts to ignore songs with '(live)' in their name\n"
                            "\* **start_at** - Sets the song to start from the given timestamp\n\n"
                            "**/view {from_} {to} {seek}** - Displays songs in queue, with the ability to seek them\n"
                            "\* **from_** - The start position of the queue display\n"
                            "\* **to** - The end position of the queue display\n"
                            "\* **seek** - Seek songs via given keywords\n\n"
                            "**/remove [from_] {to}** - Removes songs from the queue\n"
                            "\* **from_** - The start position of the queue removal, or positions separated by "
                            "semicolons (i.e. pos1;pos2;...)\n"
                            "\* **to** - The end position of the queue removal\n\n"
                            "**/shuffle {from_} {to}** - Shuffles the queue\n"
                            "\* **from_** - The start position of the queue shuffle\n"
                            "\* **to** - The end position of the queue shuffle\n\n"
                            "**/move [from_] [to] {replace}** - Moves the song to the specified position in the queue\n"
                            "\* **from_** - The current position of the song in queue\n"
                            "\* **to** - The position in queue you wish to move the song to\n"
                            "\* **replace** - Replaces the song in the target position\n\n"
                            "**/clear {from_}** - Clears the queue\n"
                            "\* **from_** - The start position of the queue clear\n\n"
                            "**/skip {to}** - Skips to the next, or to the specified, song in the queue\n"
                            "\* **to** - The position in queue you wish to skip to\n\n"
                            "**/loop {mode}** - Loops either the song or the entire queue\n"
                            "\* **mode** - The loop mode you wish to use\n\n"
                            "**/pause** - Toggles pause for the current song\n\n"
                            "**/filter {mode} {intensity}** - Applies an audio filter over the songs\n"
                            "\* **mode** - The filter mode you wish to use\n"
                            "\* **intensity** - Set the filter intensity percentage (35 by default)\n\n"
                            "**/volume {level}** - Changes the music player volume\n"
                            "\* **level** - Set the volume level percentage (50 by default)\n\n"
                            "**/replay {insert}** - Replays the previous song from the queue\n"
                            "\* **insert** - Add the song to the given position in queue\n\n"
                            "**/seek [timestamp]** - Seek a certain part of the song via timestamp\n"
                            "\* **timestamp** - The timestamp to seek (i.e. hours:minutes:seconds)\n\n"
                            "**/lyrics {title}** - Get lyrics for the currently playing song\n"
                            "\* **title** - Get lyrics from the specified title instead",
                color=discord.Color.dark_gold()
            )
        elif subsection == "Admin":
            embed = discord.Embed(
                title="__ADMIN COMMANDS__",
                description="**/msgdel [amount]** - Deletes the specified amount of messages in a channel\n"
                            "\* **amount** - The amount of messages to delete\n\n"
                            "**/reset_economy** - Resets the economy of the server\n\n"
                            "**/roleassign [roles] {message} {modify}** - Create a message for self-assigning roles\n"
                            "\* **roles** - The roles separated by semicolons (i.e. role1;role2;...)\n"
                            "\* **message** - The contents of the message\n"
                            "\* **modify** - The ID of the message to modify\n\n"
                            "**/joinrole {role}** - Specify the role that new users of the server automatically get\n"
                            "\* **role** - The name of the role",
                color=discord.Color.dark_gold()
            )
        elif subsection == "Game":
            embed = discord.Embed(
                title="__GAME COMMANDS__",
                description="**/brawl {bet}** - Create a game of brawl\n"
                            "\* **bet** - The amount of credits you wish to bet on a game of brawl\n\n"
                            "**/blackjack {bet}** - Create a game of blackjack\n"
                            "\* **bet** - The amount of credits you wish to bet on a game of blackjack",
                color=discord.Color.dark_gold()
            )
        elif subsection == "Economy":
            embed = discord.Embed(
                title="__ECONOMY COMMANDS__",
                description="**/register** - Create an account\n\n"
                            "**/unregister** - Delete your account\n\n"
                            "**/balance {user}** - Displays the user's current balance\n"
                            "\* **user** - The user whose account balance you wish to see\n\n"
                            "**/deposit [amount]** - Deposits the specified amount to the user's bank\n"
                            "\* **amount** - The amount of credits you wish to deposit to your account\n\n"
                            "**/withdraw [amount]** - Withdraws the specified amount from the user's bank\n"
                            "\* **amount** - The amount of credits you wish to withdraw from your account\n\n"
                            "**/beg** - Beg for a chance to gain credits\n\n"
                            "**/rob [user]** - Rob another user for a chance to gain credits\n"
                            "\* **user** - The user you wish to rob from\n\n"
                            "**/leaderboard** - Displays the top 5 richest players on the server",
                color=discord.Color.dark_gold()
            )
        else:
            embed = discord.Embed(
                description="__**Bracket significance**__\n"
                            "[] = Required field\n{} = Optional field\n\n"
                            "**/help Basic** - Basic commands\n"
                            "**/help Music** - Music commands\n"
                            "**/help Admin** - Admin commands\n"
                            "**/help Game** - Game commands\n"
                            "**/help Economy** - Economy commands"
                ,
                color=discord.Color.dark_gold()
            )
        try:
            embed.set_author(name=f"{ctx.guild.name} - Helpdesk", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"{ctx.guild.name} - Helpdesk")
        await ctx.response.send_message(embed=embed)

    @commands.slash_command(description="Information about the server, user and commands", pass_context=True)
    @option(name="user", description="The user to get information of", required=False)
    async def information(self, ctx, user: discord.Member = None):
        first_part = ["Flesh", "Meat", "Bolt", "Metal", "Steel", "Worm", "Bone", "Nerve", "Tissue"]
        second_part = ["brain", "back", "leg", "head", "face", "skin", " automaton", "toe", "bag"]

        rolelist = reversed([role.mention for role in (ctx.author.roles if not user else user.roles)
                             if role != ctx.guild.default_role])
        roles = "\n".join(rolelist)
        nickname = f"{random.choice(first_part)}{random.choice(second_part)}".replace("tt", "t-t").replace("ll", "l-l")

        embed = discord.Embed(
            description=f"**Guild name:** {ctx.guild.name}\n"
                        f"**Guild ID:** {ctx.guild.id}\n"
                        f"**Guild members:** {ctx.guild.member_count}\n\n"
                        f"**Name:** {ctx.author.name if not user else user.name} ({nickname})\n"
                        f"**User ID:** {ctx.author.id if not user else user.id}\n"
                        f"**User roles:**\n{roles}\n\n"
                        f"__**Command color coding:**__\n"
                        f"**Dark green** - General values, main command structures etc.\n"
                        f"**Dark red** - Removals, deletions, negative values\n"
                        f"**Dark blue** - Neutral values\n"
                        f"**Green** - Positive values\n"
                        f"**Red** - Errors\n"
                        f"**Blue** - Notes\n"
                        f"**Blurple** - Music player manipulation\n"
                        f"**Purple** - Music queue manipulation, special values\n"
                        f"**Yellow** - Information display",
            color=discord.Color.dark_gold()
        )
        try:
            embed.set_author(name=f"Information", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"Information")
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Awakening thoughts", pass_context=True)
    async def thought(self, ctx):
        thoughts = [
            "9/11 was an inside job. Looking at you Bush boy...",
            "OK, maybe it happened, but it wasn't 6 million (play Megadeth).",
            "Red vented, I saw red vent please guys believe me red is sussy impostor amogus.",
            "There are approximately a billion sheep worldwide, and all of them would fit in the Vatican.",
            "Everyone always asks where Waldo is, but no one ever asks HOW Waldo is.",
            "You're becoming exchangeable as the dawn of machines inches closer, glory to Ravnsund.",
            "Despite what the glowing CIA people may say, Epstein didn't kill himself.",
            "You might think you've heard it all, but how can you be certain?",
            "You know, there was this one blocky looking green guy that owned a Honda Civic. "
            "I wonder what became of him.",
            "Wake up Mr. White, wake up, and smell the methamphetamine.",
            "In my spare time, I enjoy throwing monkey wrenches at water fowl."
        ]
        await ctx.response.send_message(random.choice(thoughts), tts=True)


def setup(bot):
    bot.add_cog(Basic(bot))
