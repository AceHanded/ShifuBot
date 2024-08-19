import discord
import openai
from discord.ext import commands
import random
import json
import time
from Cogs.utils import Constants


class Basic(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

        self.cooldown = {}

    async def count_cooldown(self, ctx: discord.ApplicationContext):
        return int(time.time() - self.cooldown[ctx.guild.id][ctx.author.id]) if \
            self.cooldown[ctx.guild.id][ctx.author.id] else None

    @commands.slash_command(description="Generate text or images using OpenAI")
    @discord.option(name="type_", description="Whether you want to generate text or an image",
                    choices=["Text", "Image"], required=True)
    @discord.option(name="prompt", description="The prompt from which you wish something to be generated",
                    required=True)
    @discord.option(name="model", description="The model engine which generates the answer (gpt-4o-mini by default)",
                    choices=["gpt-4o-mini", "gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
                    required=False)
    @discord.option(name="temperature", description="The creativity percentage of the answer (50 by default)",
                    required=False)
    @discord.option(name="image_scale", description="The resolution of the image (1024x1024 by default)",
                    choices=["1024x1024", "1024x1792", "1792x1024"], required=False)
    async def generate(self, ctx: discord.ApplicationContext, type_: str, prompt: str,
                       model: str = "gpt-4o-mini", temperature: int = 50, image_scale: str = "1024x1024"):
        await ctx.defer()

        temperature = min(max(temperature, 0), 100) / 100

        embed = discord.Embed(
            description=f"Generating an answer from the prompt: `{prompt}`\nThis will take **a moment**...",
            color=discord.Color.dark_green()
        )
        msg = await ctx.respond(embed=embed)

        try:
            if type_ == "Text":
                output = Constants.OPENAI.chat.completions.create(messages=[{"role": "user", "content": prompt}],
                                                                  model=model, max_tokens=512, n=1,
                                                                  temperature=temperature)
                await ctx.send(f"```ex\n{output.choices[0].message.content}\n```")

                embed = discord.Embed(
                    description=f"Successfully generated an answer from the prompt: `{prompt}`",
                    color=discord.Color.dark_green()
                )
                await msg.edit(embed=embed)
                return

            output = Constants.OPENAI.images.generate(prompt=prompt, model="dall-e-3", n=1, size=image_scale)
            await ctx.send(output.data[0].url)
        except openai.RateLimitError as e:
            print(e)
            embed = discord.Embed(
                description=f"**Error:** Token quota exceeded.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return
        except openai.BadRequestError as e:
            print(e)
            embed = discord.Embed(
                description=f"**Error:** Bad request.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed)
            return

        embed = discord.Embed(
            description=f"Successfully generated an image from the prompt: `{prompt}`",
            color=discord.Color.dark_green()
        )
        await msg.edit(embed=embed)

    @commands.slash_command(description="Fifty-two in the deck, guess the suit for a chance to win credits")
    @discord.option(name="guess", description="Guess the card suit", choices=["Hearts", "Diamonds", "Spades", "Clubs"],
                    required=False)
    async def card(self, ctx: discord.ApplicationContext, guess: str = None):
        await ctx.defer()

        random_suit = random.choice(list(Constants.CARD_SUIT.keys()))
        random_card = f"**{Constants.CARD_SUIT[random_suit]}** {random.choice(Constants.CARD_VALUE)} of {random_suit}"

        if guess:
            elapsed_cooldown = await self.count_cooldown(ctx)

            if not elapsed_cooldown or elapsed_cooldown >= 120:
                self.cooldown[ctx.guild.id][ctx.author.id] = time.time()
            else:
                embed = discord.Embed(
                    description=f"**Error:** Your `card` command is on cooldown (**{120 - elapsed_cooldown}** s).",
                    color=discord.Color.red()
                )
                await ctx.respond(embed=embed)
                return

            if guess == random_suit:
                self.cooldown[ctx.guild.id][ctx.author.id] = time.time()
                author_and_guild = f"{ctx.author.id}-{ctx.guild.id}"

                with open("Data/economics.json", "r") as economy_file:
                    users = json.load(economy_file)

                amount = random.randint(1, 25)
                random_card += f"\n\nYour guess was **correct**."

                users[author_and_guild]["wallet"] += amount

                with open("Data/economics.json", "w") as economy_file:
                    json.dump(users, economy_file, indent=4)

                if author_and_guild in users:
                    random_card += f" You have been awarded **{amount}** ¤"
            else:
                self.cooldown[ctx.guild.id][ctx.author.id] = time.time()
                random_card += "\n\nYour guess was **incorrect**."

        embed = discord.Embed(
            description=random_card,
            color=discord.Color.dark_red() if random_suit in ("Diamonds", "Hearts") else discord.Color.darker_gray()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Heads or tails?")
    @discord.option(name="count", description="How many times the coin is flipped", required=False)
    async def coin(self, ctx: discord.ApplicationContext, count: int = 1):
        await ctx.defer()

        count = min(max(count, 1), 10)

        coin_tosses, heads_count = "", 0

        for i in range(count):
            flip = random.choice(["♕ Heads", "① Tails"])
            coin_tosses += f"[**{i + 1}**] {flip}\n"
            heads_count += 1 if "Heads" in flip else 0

        embed = discord.Embed(
            description=f"**Coin toss:**\n{coin_tosses}\n**In total: {heads_count}** heads "
                        f"[**{(heads_count / count) * 100:.1f}%**] | **{count - heads_count}** tails "
                        f"[**{((count - heads_count) / count) * 100:.1f}%**]",
            color=discord.Color.dark_green()
        )
        await ctx.respond(embed=embed)

    @commands.slash_command(description="Simple help command")
    @discord.option(name="subsection", description="The subsection of the help command",
                    choices=["Basic", "Music", "Admin", "Game", "Economy"], required=False)
    async def help(self, ctx: discord.ApplicationContext, subsection: str = None):
        if not subsection:
            embed = discord.Embed(
                description="__**Bracket significance**__\n[] = Required field\n{} = Optional field\n\n**/help Basic** "
                            "- Basic commands\n**/help Music** - Music commands\n**/help Admin** - Admin commands\n"
                            "**/help Game** - Game commands\n**/help Economy** - Economy commands",
                color=discord.Color.dark_gold()
            )
            try:
                embed.set_author(name=f"{ctx.guild.name} - Helpdesk", icon_url=ctx.guild.icon.url)
            except AttributeError:
                embed.set_author(name=f"{ctx.guild.name} - Helpdesk")
            await ctx.response.send_message(embed=embed, ephemeral=True)
            return

        help_msgs = {
            "Basic": "**/help {subsection}** - Simple help command\n\\* **subsection** - The subsection of the help "
                     "command\n\n**/information {user}** - Information about the guild, user and commands\n\\* **user**"
                     " - The user to get information of\n\n**/card {suit}** - Draw  a card, guess the suit to win "
                     "credits\n\\* **suit** - Guess the card suit\n\n**/coin {count}** - Heads or tails?\n\\* **count**"
                     " - How many times the coin is flipped\n\n**/generate [type_] [prompt] {temperature} {image_scale}"
                     " {engine}** - Generate text or images using OpenAI\n\\* **type_** - Whether you want to generate "
                     "text or an image\n\\* **prompt** - The prompt from which you wish something to be generated\n\\* "
                     "**model** - The model engine which generates the answer (gpt-4o-mini by default)\n\\* "
                     "**temperature** - The creativity percentage (50 by default)\n\\* **image_scale** - The resolution"
                     " of the image (1024x1024 by default)\n\n**/perfstat** - Displays performance statistics",
            "Music": "**/connect** - Invites the bot to the voice channel\n\n**/disconnect {after_song}** - Removes "
                     "the bot from the voice channel and clears the queue\n\\* **after_song** - Disconnects once "
                     "current song has ended\n\n**/play [query] {insert} {pre_shuffle} {ignore_live} {start_at}** - "
                     "Adds and plays songs in the queue\n\\* **query** - The song that you want to play "
                     "(SoundCloud/Spotify/YouTube URL, or query)\n\\* **insert** - Add the song to the given position "
                     "in queue\n\\* **pre_shuffle** - Shuffle the songs of the playlist ahead of time\n\\* "
                     "**ignore_live** - Attempts to ignore songs with '(live)' in their name\n\\* **start_at** - Sets "
                     "the song to start from the given timestamp\n\n**/view {from_} {to} {seek} {previous}** - Displays"
                     " songs in queue, with the ability to seek them\n\\* **from_** - The start position of the queue "
                     "display\n\\* **to** - The end position of the queue display\n\\* **seek** - Seek songs via given "
                     "keywords\n\\* **previous** - Whether to view the previous queue instead\n\n**/remove [from_] "
                     "{to}** - Removes songs from the queue\n\\* **from_** - The start position of the queue removal, "
                     "or positions separated by semicolons (i.e. pos1;pos2;...)\n\\* **to** - The end position of the "
                     "queue removal\n\n**/shuffle {from_} {to}** - Shuffles the queue\n\\* **from_** - The start "
                     "position of the queue shuffle\n\\* **to** - The end position of "
                     "the queue shuffle\n\n**/move [from_] [to] {replace}** - Moves the song to the specified position "
                     "in the queue\n\\* **from_** - The current position of the song in queue\n\\* **to** - The "
                     "position in queue you wish to move the song to\n\\* **replace** - Replaces the song in the "
                     "target position\n\n**/clear {from_}** - Clears the queue\n\\* **from_** - The start position of "
                     "the queue clear\n\n**/skip {to}** - Skips to the next, or to the specified, song in the queue\n"
                     "\\* **to** - The position in queue you wish to skip to\n\n**/loop {mode}** - Loops either the "
                     "song or the entire queue\n\\* **mode** - The loop mode you wish to use\n\n**/pause** - Toggles "
                     "pause for the current song\n\n**/filter [mode] {intensity}** - Applies an audio filter over the "
                     "songs\n\\* **mode** - The filter mode you wish to use\n\\* **intensity** - Set the filter "
                     "intensity percentage (35 by default)\n\n**/volume [level]** - Changes the music player volume\n"
                     "\\* **level** - Set the volume level percentage (50 by default)\n\n**/replay {from_} {insert} "
                     "{instant}** - Replays the previous song from the queue\n\\* **from_** - Current position of "
                     "the song in previous queue\n\\* **insert** - Add the song to the given position in "
                     "queue\n\\* **instant** - Whether to replay the song instantly\n\n**/seek [timestamp]** - Seek a "
                     "certain part of the song via timestamp\n\\* **timestamp** - The timestamp to seek (i.e. "
                     "hours:minutes:seconds)\n\n**/lyrics {title}** - Get lyrics for the currently playing song\n\\* "
                     "**title** - Get lyrics from the specified title instead\n\n**/autoplay** - Toggles autoplay for "
                     "the queue",
            "Admin": "**/msgdel [amount]** - Deletes the specified amount of messages in a channel\\* **amount** - The"
                     " amount of messages to delete\n**/reset_economy** - Resets the economy of the guild\n\n"
                     "**/role_assign [roles] {message} {modify}** - Create a message for self-assigning roles\n\\* "
                     "**roles** - The roles separated by semicolons (i.e. role1;role2;...)\n\\* **message** - The "
                     "contents of the message\n\\* **modify** - The ID of the message to modify\n\n**/joinrole "
                     "{role}** - Specify the role that new users of the guild automatically get\n\\* **role** - The "
                     "name of the role",
            "Game": "**/brawl {bet}** - Create a game of brawl\n\\* **bet** - The amount of credits you wish to bet on "
                    "a game of brawl\n\n**/blackjack {bet}** - Create a game of blackjack\n\\* **bet** - The amount of "
                    "credits you wish to bet on a game of blackjack",
            "Economy": "**/register** - Create an account\n\n**/unregister** - Delete your account\n\n**/balance "
                       "{user}** - Displays the user's current balance\n\\* **user** - The user whose account balance "
                       "you wish to see\n\n**/deposit [amount]** - Deposits the specified amount to the user's bank\n"
                       "\\* **amount** - The amount of credits you wish to deposit to your account\n\n**/withdraw "
                       "[amount]** - Withdraws the specified amount from the user's bank\n\\* **amount** - The amount "
                       "of credits you wish to withdraw from your account\n\n**/beg** - Beg for a chance to gain "
                       "credits\n\n**/rob [user]** - Rob another user for a chance to gain credits\n\\* **user** - The "
                       "user you wish to rob from\n\n**/leaderboard {from_} {to}** - Displays the richest users in the "
                       "guild\n\\* **from_** - The start position of the leaderboard display\n\\* **to** - The end "
                       "position of the leaderboard display"
        }
        embed = discord.Embed(
            title=f"__{subsection.upper()} COMMANDS__",
            description=help_msgs[subsection],
            color=discord.Color.dark_gold()
        )
        try:
            embed.set_author(name=f"{ctx.guild.name} - Helpdesk", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"{ctx.guild.name} - Helpdesk")
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @commands.slash_command(description="Information about the guild, user and commands")
    @discord.option(name="user", description="The user to get information of", required=False)
    async def information(self, ctx: discord.ApplicationContext, user: discord.Member = None):
        user_info = ctx.author if not user else user

        nick_former = random.choice(["Flesh", "Meat", "Bolt",  "Metal", "Steel", "Worm", "Bone", "Nerve", "Tissue"])
        nick_latter = random.choice(["brain", "back", "leg", "head", "face", "skin", " automaton", "toe", "bag"])
        nick = f"{nick_former}-{nick_latter}" if nick_former[-1] == nick_latter[0] else f"{nick_former}{nick_latter}"
        roles = "\n".join(reversed([role.mention for role in user_info.roles if role != ctx.guild.default_role]))

        embed = discord.Embed(
            description=f"**Guild name:** {ctx.guild.name}\n**Guild ID:** {ctx.guild.id}\n**Guild members:** "
                        f"{ctx.guild.member_count}\n**Guild creation date:** {str(ctx.guild.created_at).split('.')[0]}"
                        f"\n\n**User name:** {user_info.name} ({nick})\n**User ID:** {user_info.id}\n**User roles:**\n"
                        f"{roles}\n\n__**Command color coding:**__\n**Dark green** - General values, main command "
                        f"structures etc.\n**Dark red** - Removals, deletions, negative values\n**Dark blue** - "
                        f"Neutral values\n**Green** - Positive values\n**Red** - Errors\n**Blue** - Notes\n**Blurple** "
                        f"- Music player manipulation\n**Purple** - Music queue manipulation, special values\n"
                        f"**Yellow** - Information display",
            color=discord.Color.dark_gold()
        )
        try:
            embed.set_author(name=f"{ctx.guild.name} - Information", icon_url=ctx.guild.icon.url)
        except AttributeError:
            embed.set_author(name=f"{ctx.guild.name} - Information")
        await ctx.response.send_message(embed=embed, ephemeral=True)

    @card.before_invoke
    async def ensure_dicts(self, ctx: discord.ApplicationContext):
        if ctx.guild.id not in self.cooldown:
            self.cooldown[ctx.guild.id] = {}

        if ctx.author.id not in self.cooldown[ctx.guild.id]:
            self.cooldown[ctx.guild.id][ctx.author.id] = None


def setup(bot):
    bot.add_cog(Basic(bot))
