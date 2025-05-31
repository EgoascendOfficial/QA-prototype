import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
import datetime
import re
from collections import defaultdict
import asyncio
import sys
import logging
import aiohttp
import json
import random
import openai

# Set up logging for cosmic debugging 🌌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# Load environment variables from the starry .env file ✨
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
INSTAGRAM_TOKEN = os.getenv('INSTAGRAM_TOKEN')  # Add to .env for Instagram API
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY')  # Add to .env for YouTube API
# Placeholder for YouTube Channel ID - **IMPORTANT: Update this with your actual YouTube Channel ID**
YOUTUBE_CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID', 'UCYourChannelId')
openai.api_key = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN not found! A star has fallen—please set the token and try again! 🌠")
    sys.exit(1)
else:
    logger.info("DISCORD_TOKEN loaded successfully! Ready to launch into the cosmos! 🚀")

# Bot setup with intents to see the universe 👀
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
# intents.voice_states = True  # Uncomment if voice features are needed (requires audioop)

# Initialize bot with a cosmic prefix and slash command support 🌟
bot = commands.Bot(
    command_prefix='.',
    intents=intents,
    help_command=None  # Disable default help command to craft our own starry version ✨
)

# Constants for our galactic server 🌌
STAFF_ROLE_IDS = [1374320995942404216]  # Staff role ID - **IMPORTANT: Update with actual role IDs**
HELPER_ROLE_ID = 1374320995942404216  # Helper role ID - **IMPORTANT: Update with actual role ID**
MOD_LOG_CHANNEL_ID = 1374377561790087210  # Moderation log channel ID - **IMPORTANT: Update with actual channel ID**
STATUS_CHANNEL_ID = 1375511813713821727  # Status channel ID - **IMPORTANT: Update with actual channel ID**
SUGGESTION_CHANNEL_ID = 1375094650003521636  # Suggestion channel ID - **IMPORTANT: Update with actual channel ID**
SUGGESTION_CATEGORY_ID = 1376944299744301137  # Private suggestion discussion category - **IMPORTANT: Update with actual category ID**
GUIDE_CHANNEL_ID = 1376473911717400598  # Guide channel ID - **IMPORTANT: Update with actual channel ID**
MODMAIL_CHANNEL_ID = 1375161713619374140  # Modmail channel ID - **IMPORTANT: Update with actual channel ID**
VERIFICATION_CHANNEL_ID = 123456789  # Verification channel ID - **IMPORTANT: Update with correct ID**
QUARANTINE_ROLE_ID = 1374377545209872436  # Quarantine role ID - **IMPORTANT: Update with actual role ID**
BUMP_CHANNEL_ID = 1375782287613886486  # Bump reminder channel - **IMPORTANT: Update with actual channel ID**
BUMP_ROLE_ID = 1377934073250451537  # Bump role - **IMPORTANT: Update with actual role ID**
SOCIAL_MEDIA_CHANNEL_ID = 1375093303191535647  # Social media updates channel - **IMPORTANT: Update with actual channel ID**
SOCIAL_MEDIA_ROLE_ID = 1376816953901060117  # Social media ping role - **IMPORTANT: Update with actual role ID**
LINK_CHANNEL_ID = 1377973054751379627  # Resource linking channel - **IMPORTANT: Update with actual channel ID**
WELCOME_CHANNEL_ID = 1376975443147620433 # Example Welcome channel ID - **IMPORTANT: Update with actual channel ID**
DEFAULT_ROLE_ID = 1376975443147620433 # Example default role ID for new members - **IMPORTANT: Update with actual role ID**

# In-memory storage (resets on bot restart—like a supernova! 💥)
# For persistent storage, consider using a database (e.g., SQLite, PostgreSQL)
user_statuses = {}  # {user_id: status}
suggestions = []  # List of suggestions
resources = []  # List of requested resources
links = []  # List of custom links: {'trigger': str, 'notes_name': str, 'file_link': str, 'user': int, 'channel': int}
reputation = defaultdict(int)  # {user_id: points}
modmail_tickets = {}  # {ticket_id: {'user_id': str, 'status': 'open'|'closed', 'thread_id': int}}
warnings = defaultdict(list)  # {user_id: [{'case_id': int, 'reason': str, 'moderator': int, 'timestamp': datetime}]}
infractions = defaultdict(int)  # {user_id: infraction_count}
case_id_counter = 1  # For moderation case IDs
case_logs = {}  # {case_id: {'action': str, 'target': int, 'moderator': int, 'reason': str}}
quarantined_users = set()  # Set of user IDs currently quarantined
status_message = None  # To store the status message for updates
last_instagram_post = None  # Track last Instagram post ID
last_youtube_video = None  # Track last YouTube video ID

# Utility Functions to Light Up the Galaxy 🌠
async def log_action(action, target, moderator, reason, extra_info=None):
    """
    Logs moderation actions to a designated moderation log channel.
    """
    channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not channel:
        logger.error(f"Moderation log channel with ID {MOD_LOG_CHANNEL_ID} not found! A black hole must have swallowed it! 🕳️")
        return

    bot_member = channel.guild.me
    if not channel.permissions_for(bot_member).send_messages:
        logger.error(f"Bot lacks send_messages permission in mod log channel {MOD_LOG_CHANNEL_ID}!")
        return

    try:
        embed = discord.Embed(
            title=f"📜 Cosmic Log: {action}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Moderator", value=moderator.mention if moderator else "Auto-Mod 🤖", inline=False)
        if target:
            # Ensure target is a mentionable object or convert to string
            embed.add_field(name="Target", value=target.mention if isinstance(target, (discord.Member, discord.User)) else str(target), inline=False)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        if extra_info:
            embed.add_field(name="Details", value=extra_info, inline=False)
        await channel.send(embed=embed)
        logger.info(f"Logged action: {action} for {target} by {moderator}")
    except Exception as e:
        logger.error(f"Error in log_action: {str(e)}—a meteor shower disrupted the logs! ☄️")

async def notify_user(user, action, reason, duration=None):
    """
    Sends a direct message notification to a user.
    """
    try:
        if duration:
            await user.send(f"⏰ A cosmic event! You’ve been {action.lower()} in the server for {duration} seconds! Reason: {reason} 📜 Let’s align the stars better next time! 🌟")
        else:
            await user.send(f"🚨 A galactic notice! You’ve been {action.lower()} in the server! Reason: {reason} 📜 Let’s keep the universe harmonious! 🌟")
    except discord.Forbidden:
        logger.warning(f"Could not notify {user.id}: Bot is blocked or user has DMs disabled. Their star is out of reach! 🌠")

async def check_bot_permissions(ctx, required_perms):
    """
    Checks if the bot has the necessary permissions in a given context.
    """
    bot_member = ctx.guild.me
    bot_perms = bot_member.guild_permissions
    missing_perms = [perm for perm, value in required_perms.items() if not getattr(bot_perms, perm)]
    if missing_perms:
        await ctx.send(f"⚠️ My cosmic powers are limited! I need these permissions: {', '.join(missing_perms)}. Please adjust my role in the galaxy! 🛠️")
        return False
    # Ensure bot's role is higher than the roles it's managing
    bot_top_role = bot_member.top_role
    if 'manage_roles' in required_perms:
        roles_to_manage = []
        quarantine_role = ctx.guild.get_role(QUARANTINE_ROLE_ID)
        if quarantine_role:
            roles_to_manage.append(quarantine_role)
        verified_role = discord.utils.get(ctx.guild.roles, name="Verified") # Assuming a 'Verified' role exists
        if verified_role:
            roles_to_manage.append(verified_role)

        for role in roles_to_manage:
            if role and bot_top_role.position <= role.position:
                await ctx.send(f"⚠️ My highest role ({bot_top_role.name}) must be above the roles I’m managing (e.g., Quarantine, Verified)! Please adjust the cosmic hierarchy! 🛠️")
                return False
    return True

async def update_status_board():
    """
    Updates the status board message in the designated status channel.
    """
    global status_message
    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if not channel:
        logger.error(f"Status channel with ID {STATUS_CHANNEL_ID} not found! It’s lost in the cosmos! 🌌")
        return

    bot_member = channel.guild.me
    channel_perms = channel.permissions_for(bot_member)
    if not (channel_perms.send_messages and channel_perms.manage_messages and channel_perms.read_message_history):
        logger.error(f"Bot lacks permissions in status channel {STATUS_CHANNEL_ID}: send_messages={channel_perms.send_messages}, manage_messages={channel_perms.manage_messages}, read_message_history={channel_perms.read_message_history}")
        return

    embed = discord.Embed(
        title="🌟 Status Galaxy 🌟",
        description="Behold the twinkling statuses of our cosmic community! 🚀",
        color=discord.Color.green(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    if not user_statuses:
        embed.add_field(name="🌌 Cosmic Void", value="The galaxy is silent... Set your status with `.f`, `.s`, etc., to light up the stars! ✨", inline=False)
    else:
        for user_id, status in list(user_statuses.items()):
            user = bot.get_user(user_id)
            if user:
                embed.add_field(name=f"🌠 {user.display_name}", value=status, inline=True)
            else:
                # Remove user if not found (e.g., left the guild)
                user_statuses.pop(user_id, None)

    try:
        if status_message:
            try:
                await status_message.edit(embed=embed)
                logger.info("Status board updated successfully! The stars are aligned! 🌟")
                return
            except discord.NotFound:
                logger.warning("Status message not found. Creating a new one in the cosmos! ✨")
                status_message = None
            except discord.Forbidden:
                logger.error("Bot lacks permission to edit the status message! A galactic oversight! 🚫")
                status_message = None # Reset to create a new one
                return

        # Try to find an existing status message if status_message is None or was not found
        async for msg in channel.history(limit=100):
            if msg.author == bot.user and msg.embeds and msg.embeds[0].title == "🌟 Status Galaxy 🌟":
                status_message = msg
                await status_message.edit(embed=embed)
                logger.info("Found and updated existing status message! The galaxy shines brighter! 🌠")
                return

        # If no existing message was found, send a new one
        status_message = await channel.send(embed=embed)
        logger.info("Created a new status message! A new star is born! 🌟")
    except Exception as e:
        logger.error(f"Error updating status board: {str(e)}—a cosmic storm disrupted the update! ⛈️")
        await log_action("Error in update_status_board", None, None, str(e))

# --- Custom Help View ---
class HelpView(discord.ui.View):
    def __init__(self, bot_instance, user, commands_list, specific_command=None):
        super().__init__(timeout=180)
        self.bot = bot_instance # Renamed to avoid conflict with global 'bot'
        self.user = user
        self.commands_list = commands_list
        self.specific_command = specific_command
        self.current_page = 0
        self.commands_per_page = 5
        self.message = None # To store the message for editing

        total_pages = (len(commands_list) + self.commands_per_page - 1) // self.commands_per_page
        if self.specific_command or total_pages <= 1:
            # Remove pagination buttons if a specific command is shown or only one page
            for item in self.children:
                if isinstance(item, discord.ui.Button) and (item.label == "⬅️ Previous" or item.label == "Next ➡️"):
                    self.remove_item(item)

    async def get_embed(self):
        embed = discord.Embed(
            title="🌟 Cosmic Command Guide 🌟",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Requested by {self.user.display_name}", icon_url=self.user.avatar.url if self.user.avatar else None)

        if self.specific_command:
            cmd = self.specific_command
            description = getattr(cmd, 'description', 'No description available in the cosmos.')
            usage = getattr(cmd, 'usage', f".{cmd.name}")
            aliases = getattr(cmd, 'aliases', [])
            embed.add_field(
                name=f"📜 {cmd.name.title()}",
                value=f"**Description:** {description}\n**Usage:** `{usage}`\n**Aliases:** {', '.join(aliases) if aliases else 'None'}",
                inline=False
            )
        else:
            start = self.current_page * self.commands_per_page
            end = start + self.commands_per_page
            page_commands = self.commands_list[start:end]

            embed.description = "Explore the starry commands to navigate our galaxy! ✨\nUse `.help <command>` or `.help<command>` (e.g., `.helpwarn`) to dive deeper into a specific command’s orbit!"
            
            if not page_commands:
                embed.add_field(name="No commands found", value="It seems there are no commands to display on this page.", inline=False)
            else:
                for cmd_name, cmd in page_commands:
                    description = getattr(cmd, 'description', 'No description available in the cosmos.')
                    embed.add_field(
                        name=f"🌠 .{cmd_name}",
                        value=f"{description}\n**Individual Help:** `.help {cmd_name}`",
                        inline=False
                    )

            total_pages = (len(self.commands_list) + self.commands_per_page - 1) // self.commands_per_page
            embed.set_footer(
                text=f"Page {self.current_page + 1}/{total_pages} | Requested by {self.user.display_name}",
                icon_url=self.user.avatar.url if self.user.avatar else None
            )

        return embed

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Only the cosmic traveler who requested this guide can navigate the stars! 🌠", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Only the cosmic traveler who requested this guide can navigate the stars! 🌠", ephemeral=True)
            return

        total_pages = (len(self.commands_list) + self.commands_per_page - 1) // self.commands_per_page
        self.current_page = min(total_pages - 1, self.current_page + 1)
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

# --- Resource View ---
class ResourceView(discord.ui.View):
    def __init__(self, user, resources):
        super().__init__(timeout=180)
        self.user = user
        self.resources = resources
        self.current_page = 0
        self.resources_per_page = 5
        self.message = None # To store the message for editing

        total_pages = (len(resources) + self.resources_per_page - 1) // self.resources_per_page
        if total_pages <= 1:
            for item in self.children:
                if isinstance(item, discord.ui.Button) and (item.label == "⬅️ Previous" or item.label == "Next ➡️"):
                    self.remove_item(item)

    async def get_embed(self):
        embed = discord.Embed(
            title="📚 Cosmic Library 🌌",
            description="Here are the resources requested by our starry community! ✨",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        start = self.current_page * self.resources_per_page
        end = start + self.resources_per_page
        page_resources = self.resources[start:end]

        if not page_resources:
            embed.add_field(name="🌌 Cosmic Void", value="The library is empty... Request resources with 'I want <resource> of <board>'! 📖", inline=False)
        else:
            for idx, res in enumerate(page_resources, start=start + 1):
                user = bot.get_user(res['user'])
                channel = bot.get_channel(res['channel'])
                embed.add_field(
                    name=f"📜 Resource #{idx}",
                    value=f"**Resource:** {res['resource']}\n**Board:** {res['board']}\n**Requested by:** {user.mention if user else 'Unknown User'}\n**Channel:** {channel.mention if channel else 'Unknown Channel'}",
                    inline=False
                )

        total_pages = (len(self.resources) + self.resources_per_page - 1) // self.resources_per_page
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{total_pages} | Requested by {self.user.display_name}",
            icon_url=self.user.avatar.url if self.user.avatar else None
        )
        return embed

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Only the cosmic traveler who requested this library can turn the pages! 📚", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("🚫 Only the cosmic traveler who requested this library can turn the pages! 📚", ephemeral=True)
            return

        total_pages = (len(self.resources) + self.resources_per_page - 1) // self.resources_per_page
        self.current_page = min(total_pages - 1, self.current_page + 1)
        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

# --- Social Media Button View ---
class SocialMediaView(discord.ui.View):
    def __init__(self, post_url):
        super().__init__(timeout=None)  # Persistent view
        self.add_item(discord.ui.Button(label="View Post", style=discord.ButtonStyle.link, url=post_url))

# --- Event Handlers ---
@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected to Discord.
    Performs initial setup, syncs slash commands, updates status board, and initializes social media tracking.
    """
    global status_message, last_instagram_post, last_youtube_video
    logger.info(f'Bot is online as {bot.user}! 🌟 Ready to make your server a magical constellation! 🪄')
    activity = discord.Activity(type=discord.ActivityType.watching, name="The Resource Repository 📚")
    await bot.change_presence(activity=activity)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Slash commands synced successfully: {len(synced)} commands are now shining in the galaxy! 🌟")
        await update_status_board()
        # Initialize social media tracking
        async with aiohttp.ClientSession() as session:
            # Instagram
            if INSTAGRAM_TOKEN:
                instagram_api_url = f"https://graph.instagram.com/me/media?fields=id,caption,media_url,permalink,timestamp&access_token={INSTAGRAM_TOKEN}"
                async with session.get(instagram_api_url) as resp:
                    if resp.status == 200: # Use .status for aiohttp.ClientResponse
                        data = await resp.json()
                        if data.get('data'):
                            last_instagram_post = data['data'][0]['id']
                            logger.info(f"Initialized last Instagram post: {last_instagram_post}")
                        else:
                            logger.warning("Instagram API returned no data.")
                    else:
                        logger.warning(f"Failed to fetch Instagram posts: HTTP {resp.status} - {await resp.text()}")
            else:
                logger.info("Instagram token not set. Skipping Instagram updates.")

            # YouTube
            if YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID and YOUTUBE_CHANNEL_ID != 'UCYourChannelId':
                youtube_api_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&maxResults=1&order=date&key={YOUTUBE_API_KEY}"
                async with session.get(youtube_api_url) as resp:
                    if resp.status == 200: # Use .status for aiohttp.ClientResponse
                        data = await resp.json()
                        if data.get('items'):
                            last_youtube_video = data['items'][0]['id']['videoId']
                            logger.info(f"Initialized last YouTube video: {last_youtube_video}")
                        else:
                            logger.warning("YouTube API returned no data.")
                    else:
                        logger.warning(f"Failed to fetch YouTube videos: HTTP {resp.status} - {await resp.text()}")
            else:
                if not YOUTUBE_API_KEY:
                    logger.info("YouTube API key not set. Skipping YouTube updates.")
                elif YOUTUBE_CHANNEL_ID == 'UCYourChannelId':
                    logger.warning("YouTube Channel ID not updated. Skipping YouTube updates.")

        # Start tasks
        bump_reminder.start()
        check_social_media.start()
    except discord.errors.Forbidden:
        logger.error("Failed to sync slash commands: Missing applications.commands scope. Please re-invite the bot with the correct scope! 🚫")
    except Exception as e:
        logger.error(f"Error in on_ready: {str(e)}—a cosmic storm disrupted startup! ⛈️")

@bot.event
async def on_message(message):
    """
    Processes incoming messages for auto-responses, reputation, modmail, and other features.
    """
    if message.author.bot:
        return

    try:
        content_lower = message.content.lower()

        # Creative Auto-Responders
        greetings = ['hello', 'hi', 'hey']
        farewells = ['bye', 'goodbye', 'see ya']
        morning = ['good morning', 'morning']
        night = ['good night', 'night']
        
        responses = [
            f"🌠 Yo, {message.author.mention}! What's good in the galaxy? 🚀",
            f"✨ Hey there, {message.author.mention}! Ready to explore the cosmos? 🌌",
            f"🪐 Greetings, {message.author.mention}! Let's make some starry magic! 🪄"
        ]
        farewell_responses = [
            f"🌌 Catch you later, {message.author.mention}! Fly safe among the stars! ✨",
            f"💫 Farewell, {message.author.mention}! May your cosmic journey be epic! 🚀"
        ]
        morning_responses = [
            f"☀️ Rise and shine, {message.author.mention}! A new day in the galaxy awaits! 🌟",
            f"🌅 Good morning, {message.author.mention}! Let’s conquer the cosmos today! 🚀"
        ]
        night_responses = [
            f"🌙 Sweet dreams, {message.author.mention}! Sleep tight under the starry sky! 💤",
            f"✨ Good night, {message.author.mention}! May your dreams be out of this world! 🌌"
        ]

        if any(g in content_lower for g in greetings):
            await message.channel.send(random.choice(responses))
        elif any(f in content_lower for f in farewells):
            await message.channel.send(random.choice(farewell_responses))
        elif any(m in content_lower for m in morning):
            await message.channel.send(random.choice(morning_responses))
        elif any(n in content_lower for n in night):
            await message.channel.send(random.choice(night_responses))

        # Reputation System
        if message.reference and ('thanks' in content_lower or 'tysm' in content_lower or 'thank you' in content_lower):
            try:
                replied_message = await message.channel.fetch_message(message.reference.message_id)
                if replied_message.author != message.author and not replied_message.author.bot:
                    helper = replied_message.author
                    thanker = message.author
                    reputation[helper.id] += 1
                    await message.channel.send(f"🌟 {helper.mention}, you’re a galactic hero! {thanker.mention} thanked you, earning you +1 rep point! ✨")
                    await log_action("Reputation Awarded", helper, thanker, f"{thanker.display_name} thanked {helper.display_name} (+1 rep)")
            except discord.NotFound:
                await message.channel.send("⚠️ The message you replied to vanished into a black hole! Couldn’t award rep points. 🕳️")

        # Status-Based Ping Response
        if message.mentions and not isinstance(message.channel, discord.DMChannel):
            for user in message.mentions:
                if user.id in user_statuses:
                    status = user_statuses[user.id]
                    status_responses = { # Renamed to avoid conflict
                        "Free ✅": f"🌟 {user.mention} is Free ✅—ready to chat and light up the galaxy! 🗣️",
                        "Sleeping 😴": f"💤 {user.mention} is Sleeping 😴—dreaming in a nebula! They’ll reply soon! 🌙",
                        "Do Later 🚧": f"⏳ {user.mention} is Do Later 🚧—on a cosmic mission! Catch them later! 🪐",
                        "Studying 📚": f"📖 {user.mention} is Studying 📚—diving into knowledge! They’ll reply after! 🧠",
                        "Outside 🚶‍♂️": f"🌳 {user.mention} is Outside 🚶‍♂️—stargazing IRL! They’ll be back! 🍃",
                        "On Break ☕": f"☕ {user.mention} is On Break ☕—chilling in a nebula lounge! They’ll chat soon! 🛋️"
                    }
                    if status in status_responses:
                        await message.channel.send(status_responses[status])
                        
        if hasattr(message, "mentions") and bot.user in message.mentions and not message.author.bot:
            prompt: str = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
            if not prompt:
                await message.channel.send("Hi there! You mentioned me — what's up?")
                return

            try:
                await message.channel.typing()
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful, friendly, and casual AI assistant in a Discord server. Reply like a normal human. Keep it brief, natural, and clear."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.7
                )
                ai_reply = response.choices[0].message.content.strip()
                await message.channel.send(ai_reply)

            except Exception as e:
                logger.error(f"AI reply error: {e}")
                await message.channel.send("Oops, something went wrong. Try again soon!")


        # Past Paper Search (Mock Response)
        match = re.search(r'past paper (\w+) (\d{4})', content_lower)
        if match:
            subject, year = match.groups()
            await message.channel.send(f"📜 Searching the cosmic archives for {subject} past papers from {year}! 🕰️ Check back soon for links! 📚")
            # In a real implementation, integrate with an external API or database
            # Example: Fetching from a Google Drive folder or a custom API
            # For demonstration, this remains a mock response.

        # Helper Ping
        if 'help me' in content_lower and not isinstance(message.channel, discord.DMChannel):
            helper_role = message.guild.get_role(HELPER_ROLE_ID)
            if helper_role:
                await message.channel.send(f"🆘 Cosmic SOS! {helper_role.mention}, {message.author.mention} needs your stellar help! 🦸‍♂️")
                await log_action("Helper Ping", message.author, None, "User requested help with 'help me'")
            else:
                await message.channel.send(f"⚠️ Helper role not found! Please set up the role with ID {HELPER_ROLE_ID}! 🕳️")

        # Resource Linking
        if message.channel.id == LINK_CHANNEL_ID:
            match = re.search(r'i want (\w+) of (\w+)', content_lower)
            if match:
                resource, board = match.groups()
                resources.append({'resource': resource, 'board': board, 'user': message.author.id, 'channel': message.channel.id})
                await message.channel.send(f"📚 Added {resource} for {board} to the cosmic library! 🌌 View with `.listlink`! 📖")

        # Custom Link Trigger
        for link in links:
            if link['trigger'] in content_lower:
                hyperlink = f"[{link['notes_name']}]({link['file_link']})"
                await message.channel.send(f"📎 Found a cosmic link! Notes: {hyperlink} for {link['notes_name']}! 🌟")
                await log_action("Link Triggered", message.author, None, f"Trigger: {link['trigger']}, Notes: {link['notes_name']}, Link: {link['file_link']}")
                break

        # Modmail System
        if isinstance(message.channel, discord.DMChannel):
            ticket_id = None
            # Find an existing open ticket for this user
            for tid, ticket_data in modmail_tickets.items():
                if ticket_data['user_id'] == str(message.author.id) and ticket_data['status'] == 'open':
                    ticket_id = tid
                    break

            modmail_channel = bot.get_channel(MODMAIL_CHANNEL_ID)
            if not modmail_channel:
                await message.channel.send(f"⚠️ Modmail channel not found! Please inform staff to set up channel ID {MODMAIL_CHANNEL_ID}. 🕳️")
                return

            bot_member_in_guild = modmail_channel.guild.get_member(bot.user.id)
            if not bot_member_in_guild:
                logger.error(f"Bot member not found in guild {modmail_channel.guild.id} for modmail operations.")
                await message.channel.send("⚠️ The bot is not properly set up in the server for modmail. Please inform staff! 🛠️")
                return

            channel_perms = modmail_channel.permissions_for(bot_member_in_guild)
            if not channel_perms.manage_threads:
                await message.channel.send("⚠️ I need `manage_threads` permission in the modmail channel to create tickets! 🛠️")
                return

            if not ticket_id:
                # No open ticket found, create a new one
                try:
                    # Increment case_id_counter for a unique ticket_id
                    global case_id_counter
                    new_ticket_id = case_id_counter
                    case_id_counter += 1

                    thread = await modmail_channel.create_thread(
                        name=f"🌟 Modmail Ticket #{new_ticket_id} - {message.author.name}",
                        auto_archive_duration=1440, # Archive after 24 hours of inactivity
                        type=discord.ChannelType.private_thread # For private discussions with staff
                    )
                    
                    # Add user to the thread
                    await thread.add_user(message.author)
                    
                    # Add staff members to the thread
                    for member in modmail_channel.guild.members:
                        if any(role.id in STAFF_ROLE_IDS for role in member.roles):
                            await thread.add_user(member)

                    modmail_tickets[str(new_ticket_id)] = { # Store as string key
                        'user_id': str(message.author.id),
                        'status': 'open',
                        'thread_id': thread.id
                    }
                    await message.channel.send(f"📮 📖 Ticket #{new_ticket_id} opened! The cosmic crew will reply soon! 🌠")
                    await log_action("Modmail Ticket Created", message.author, None, f"Ticket #{new_ticket_id} opened")
                    ticket_id = str(new_ticket_id) # Set current ticket_id

                except discord.Forbidden:
                    await message.channel.send("⚠️ I need `manage_threads` permission in the modmail channel to create tickets! 🛠️")
                    return
                except Exception as e:
                    logger.error(f"Error creating modmail ticket: {str(e)}")
                    await message.channel.send(f"⚠️ Failed to create modmail ticket: {str(e)}. Try again! 🌟")
                    await log_action("Error creating modmail ticket", message.author, None, str(e))
                    return
            
            # Now, handle the message for the existing or newly created ticket
            ticket = modmail_tickets[ticket_id]
            thread = discord.utils.get(modmail_channel.threads, id=ticket['thread_id'])
            
            # If thread not found (e.g., deleted or bot restarted without proper persistence), try to refetch or create a new one
            if not thread:
                try:
                    thread = await modmail_channel.guild.fetch_channel(ticket['thread_id'])
                except discord.NotFound:
                    logger.warning(f"Modmail thread {ticket['thread_id']} not found, attempting to recreate.")
                    # Recreate thread if not found, but it's better to make this more robust
                    # This is a fallback; persistent storage would avoid this
                    await message.channel.send(f"⚠️ Warning: associated modmail thread for ticket #{ticket_id} not found. Attempting to recreate... 🕳️")
                    
                    try:
                        staff_role = modmail_channel.guild.get_role(STAFF_ROLE_IDS[0])
                        if not staff_role:
                            await message.channel.send(f"⚠️ Staff role (ID: {STAFF_ROLE_IDS[0]}) not found! Please inform staff! 🌟")
                            return

                        thread = await modmail_channel.create_thread(
                            name=f"🌟 Modmail Ticket #{ticket_id} - {message.author.name}",
                            auto_archive_duration=1440,
                            type=discord.ChannelType.private_thread
                        )
                        await thread.add_user(message.author)
                        for member in modmail_channel.guild.members:
                            if any(role.id in STAFF_ROLE_IDS for role in member.roles): # Corrected: `member.roles`
                                await thread.add_user(member)
                        ticket['thread_id'] = thread.id # Update thread ID in stored data
                        await message.channel.send(f"✅ Recreated thread for ticket #{ticket_id}. Please resend your message if it wasn't delivered.")
                        await log_action("Modmail Thread Recreated", message.author, None, f"Thread recreated for ticket #{ticket_id}")
                    except Exception as e:
                        logger.error(f"Failed to recreate modmail thread for ticket {ticket_id}: {e}")
                        await message.channel.send(f"⚠️ Failed to recreate modmail thread. Please contact staff directly or try again later. 🛠️")
                        return

            if ticket['status'] != 'open':
                await message.channel.send(f"🔒 Ticket #{ticket_id} is closed. Wait for staff to reopen or start a new conversation with `.modmail`! 🌌")
                return

            embed = discord.Embed(
                title=f"📬 Ticket #{ticket_id} Message from User",
                description=message.content,
                color=discord.Color.purple(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else '')
            await thread.send(embed=embed)

        # Staff Modmail Replies
        if isinstance(message.channel, discord.Thread) and message.channel.parent_id == MODMAIL_CHANNEL_ID:
            ticket_id_found = None
            for tid, ticket_data in modmail_tickets.items():
                if ticket_data['thread_id'] == message.channel.id:
                    ticket_id_found = tid
                    break

            if not ticket_id_found:
                await message.channel.send("⚠️ This thread isn’t an active modmail ticket! Please report this error if it persists. 🛠️")
                return

            ticket = modmail_tickets[ticket_id_found]
            if ticket['status'] != 'open':
                await message.channel.send("🔒 This ticket is closed! Use `.modmailopen <ticket_id>` to reopen! 🔓")
                return

            # Prevent bot replies from being sent back to the user via modmail
            if message.author.bot:
                return

            # Check if the author is a staff member
            if message.guild and any(role.id in STAFF_ROLE_IDS for role in message.author.roles):
                user = await bot.fetch_user(int(ticket['user_id'])) # Using fetch_user for more robust user retrieval
                if not user:
                    await message.channel.send("⚠️ User not found! They may have left the server. Cannot send reply. 🌌")
                    return

                embed = discord.Embed(
                    title=f"📡 Ticket #{ticket_id_found} Reply from Staff",
                    description=message.content,
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                )
                embed.set_author(name=message.author.display_name, icon_url=message.author.avatar.url if message.author.avatar else None)
                try:
                    await user.send(embed=embed)
                    await message.add_reaction("✅") # React with a checkmark to confirm sending
                    await log_action("Modmail Reply Sent", user, message.author, f"Ticket #{ticket_id_found}: {message.content}")
                except discord.Forbidden:
                    await message.channel.send(f"⚠️ Could not send reply to {user.display_name}! Their DMs are disabled. 📖️")
                    await message.add_reaction("❌") # React with an X to indicate failure
                except Exception as e:
                    logger.error(f"Error sending modmail reply: {e}")
                    await message.channel.send(f"⚠️ An error occurred while sending the reply: {e}. Please try again.")
                    await message.add_reaction("❌")

    except Exception as e:
        logger.error(f"Error in on_message: {str(e)}")
        await message.channel.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again or contact support! 🚖")
        # Log the error, but be careful not to create a recursive loop if logging itself fails
        await log_action("Error in on_message", message.author, None, str(e))

    await bot.process_commands(message) # Process commands after custom message handling

@bot.event
async def on_member_join(member):
    """
    Handles new member joins: sends a welcome message and assigns a default role.
    """
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        welcome_embed = discord.Embed(
            title=f"✨ Welcome to the Cosmic Galaxy, {member.name}! ✨",
            description=f"We're thrilled to have you here! Explore the channels, say hello, and embark on your galactic journey. Check out {bot.get_channel(GUIDE_CHANNEL_ID).mention if bot.get_channel(GUIDE_CHANNEL_ID) else 'the guide channel'} to get started!",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        welcome_embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        welcome_embed.add_field(name="🚀 Get Started", value="Type `.help` to see all commands!", inline=False)
        
        try:
            await welcome_channel.send(f"Welcome {member.mention}!", embed=welcome_embed)
            logger.info(f"Sent welcome message to {member.name}")
        except discord.Forbidden:
            logger.error(f"Bot lacks permission to send messages in welcome channel {WELCOME_CHANNEL_ID}!")
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")

    default_role = member.guild.get_role(DEFAULT_ROLE_ID)
    if default_role:
        try:
            # Check bot's permissions before attempting to assign role
            bot_member = member.guild.me
            if bot_member.top_role.position > default_role.position and bot_member.guild_permissions.manage_roles:
                await member.add_roles(default_role)
                logger.info(f"Assigned default role '{default_role.name}' to {member.name}")
            else:
                logger.warning(f"Could not assign default role to {member.name}. Bot role too low or missing 'manage_roles' permission.")
        except discord.Forbidden:
            logger.error(f"Bot lacks permission to assign roles in guild {member.guild.name}!")
        except Exception as e:
            logger.error(f"Error assigning default role: {e}")


# --- Tasks ---
@tasks.loop(hours=2)
async def bump_reminder():
    """
    Sends a bump reminder message in the designated bump channel.
    """
    channel = bot.get_channel(BUMP_CHANNEL_ID)
    role = channel.guild.get_role(BUMP_ROLE_ID) if channel else None

    if not channel or not role:
        logger.error(f"Either bump channel {BUMP_CHANNEL_ID} or role {BUMP_ROLE_ID} not found for bump reminder!")
        return

    bot_member = channel.guild.me
    # Corrected permission check
    if not channel.permissions_for(bot_member).send_messages:
        logger.error(f"Bot lacks permission to send bump reminder in channel {BUMP_CHANNEL_ID}!")
        return
    try:
        await channel.send(f"▴ **Bump Reminder**\nThe server can be bumped again!\n{role.mention}, bump the server by using `/bump`! 😖")
        await log_action("Bump Reminder", None, None, f"Sent bump reminder in {channel.name}")
    except discord.Forbidden:
        logger.error(f"Bot lacks permission to send bump reminder in channel {BUMP_CHANNEL_ID}! 🚖")
    except Exception as e:
        logger.error(f"Error in bump_reminder: {str(e)}")
        await log_action("Error in bump_reminder", None, None, str(e))

@tasks.loop(minutes=30)
async def check_social_media():
    """
    Checks for new Instagram posts and YouTube videos and posts them to the social media channel.
    """
    global last_instagram_post, last_youtube_video
    channel = bot.get_channel(SOCIAL_MEDIA_CHANNEL_ID)
    role = channel.guild.get_role(SOCIAL_MEDIA_ROLE_ID) if channel else None

    if not channel or not role:
        logger.error(f"Either Social media channel {SOCIAL_MEDIA_CHANNEL_ID} or role {SOCIAL_MEDIA_ROLE_ID} not found! Skipping social media checks.")
        return

    bot_member = channel.guild.me
    if not channel.permissions_for(bot_member).send_messages:
        logger.error(f"Bot lacks send_messages permission in social media channel {SOCIAL_MEDIA_CHANNEL_ID}! Skipping social media checks.")
        return

    async with aiohttp.ClientSession() as session:
        try:
            # Instagram
            if INSTAGRAM_TOKEN:
                instagram_api_url = f"https://graph.instagram.com/me/media?fields=id,caption,media_url,permalink,timestamp&access_token={INSTAGRAM_TOKEN}"
                async with session.get(instagram_api_url) as resp:
                    if resp.status == 200: # Use .status for aiohttp.ClientResponse
                        data = await resp.json()
                        if data.get('data'):
                            latest_post = data['data'][0]
                            if last_instagram_post and latest_post['id'] != last_instagram_post:
                                embed = discord.Embed(
                                    title="🌟 New Instagram Post! 📸", # Changed emoji for clarity
                                    description=latest_post.get('caption', 'Check out our latest post!'),
                                    color=discord.Color.purple(),
                                    timestamp=datetime.datetime.fromisoformat(latest_post['timestamp'].replace('Z', '+00:00')) # Parse ISO format timestamp
                                )
                                embed.set_image(url=latest_post['media_url'])
                                embed.set_footer(text="Follow us on Instagram: @your_instagram_handle") # Update Instagram handle
                                view = SocialMediaView(latest_post['permalink'])
                                await channel.send(f"{role.mention} A new post just landed on Instagram! 📖", embed=embed, view=view)
                                await log_action("Instagram Update", None, None, reason=f"New post: {latest_post['id']}")
                                last_instagram_post = latest_post['id']
                            elif not last_instagram_post:
                                last_instagram_post = latest_post['id'] # Initialize if it's the first run
                        else:
                            logger.warning("Instagram API returned no data.")
                    else:
                        logger.warning(f"Failed to fetch Instagram posts: HTTP {resp.status} - {await resp.text()}")
            else:
                logger.info("Instagram token not set. Skipping Instagram updates.")

            # YouTube
            if YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID and YOUTUBE_CHANNEL_ID != 'UCYourChannelId':
                youtube_api_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={YOUTUBE_CHANNEL_ID}&maxResults=1&order=date&key={YOUTUBE_API_KEY}"
                async with session.get(youtube_api_url) as resp:
                    if resp.status == 200: # Use .status for aiohttp.ClientResponse
                        data = await resp.json()
                        if data.get('items'):
                            latest_video = data['items'][0]
                            video_id = latest_video['id']['videoId']
                            if last_youtube_video and video_id != last_youtube_video:
                                embed = discord.Embed(
                                    title="🎥 New YouTube Video! 🌟",
                                    description=latest_video['snippet']['title'], # Corrected: Access title from snippet
                                    color=discord.Color.red(),
                                    timestamp=datetime.datetime.fromisoformat(latest_video['snippet']['publishedAt'].replace('Z', '+00:00')) # Corrected: Access from snippet, parse timestamp
                                )
                                embed.set_image(url=latest_video['snippet']['thumbnails']['high']['url']) # Corrected: Access from snippet
                                embed.set_footer(text="Subscribe: @your_youtube_channel_handle") # Update YouTube handle
                                view = SocialMediaView(f"https://www.youtube.com/watch?v={video_id}") # Corrected YouTube URL
                                await channel.send(f"{role.mention} A new video just dropped on YouTube! 🚖", embed=embed, view=view)
                                await log_action("YouTube Update", None, None, f"New video: {video_id}")
                                last_youtube_video = video_id # Corrected: Use last_youtube_video
                            elif not last_youtube_video:
                                last_youtube_video = video_id # Initialize if it's the first run
                        else:
                            logger.warning("YouTube API returned no data.")
                    else:
                        logger.warning(f"Failed to fetch YouTube videos: HTTP {resp.status} - {await resp.text()}")
            else:
                if not YOUTUBE_API_KEY:
                    logger.info("YouTube API key not set. Skipping YouTube updates.")
                elif YOUTUBE_CHANNEL_ID == 'UCYourChannelId':
                    logger.warning("YouTube Channel ID not updated. Skipping YouTube updates.")
        except Exception as e:
            logger.error(f"Error in check_social_media: {str(e)}")
            await log_action("Error in check_social_media", None, None, str(e))

# --- Help Commands ---
@bot.command(name='help')
async def help_command(ctx, *, command_name: str = None):
    """
    Display this help menu or info about a specific command.
    Usage: .help [command_name]
    """
    try:
        # Filter out individual help commands and the main help command itself if not showing specific help
        all_commands = []
        for cmd in bot.commands:
            if not cmd.hidden: # Consider adding a `hidden=True` attribute to commands you don't want in general help
                all_commands.append((cmd.name, cmd))
        
        all_commands.sort(key=lambda x: x[0])

        if command_name:
            command_name = command_name.lower().lstrip('.') # Remove leading dot if present
            cmd = bot.get_command(command_name)
            if not cmd:
                await ctx.send(f"⚠️ Command `.{command_name}` not found! Try `.help` for all commands. 😖")
                return
            view = HelpView(bot, ctx.author, all_commands, specific_command=cmd)
        else:
            view = HelpView(bot, ctx.author, all_commands)
        
        embed = await view.get_embed()
        view.message = await ctx.send(embed=embed, view=view) # Store message for pagination
    except Exception as e:
        logger.error(f"Error in help_command: {str(e)}")
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again or contact support! 🚖")
        await log_action("Error in help_command", ctx.author, None, str(e))
help_command.description = "Display this help menu or info about a specific command."
help_command.usage = ".help [command]"


@bot.command(name='helpallcmd', aliases=['allcommands', 'commands'])
async def help_all_commands(ctx):
    """
    List all available commands in a compact format.
    Usage: .helpallcmd
    """
    try:
        commands_list_for_display = []
        for cmd in bot.commands:
            if not cmd.hidden:
                commands_list_for_display.append(f"`.{cmd.name}` - {getattr(cmd, 'description', 'No description.')}")
        
        commands_text = "\n".join(commands_list_for_display)
        if not commands_text:
            commands_text = "No commands registered yet."

        embed = discord.Embed(
            title="🌟 All Cosmic Commands 🌟",
            description=f"A constellation of all commands! ✨ Use `.help <command>` for details!\n\n{commands_text}",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        await ctx.send(embed=embed)
    except Exception as e:
        logger.error(f"Error in help_all_commands: {str(e)}")
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in help_all_commands", ctx.author, None, str(e))
help_all_commands.description = "List all available commands."
help_all_commands.usage = ".helpallcmd"

# --- Moderation Commands ---

def is_staff():
    """Custom check to see if the user has a staff role."""
    async def predicate(ctx):
        if not ctx.guild:
            return False
        return any(role.id in STAFF_ROLE_IDS for role in ctx.author.roles)
    return commands.check(predicate)

@bot.command(name='warn')
@is_staff()
async def warn(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Warns a user and logs the warning.
    Usage: .warn <user> [reason]
    """
    global case_id_counter
    try:
        case_id = case_id_counter
        case_id_counter += 1
        warnings[member.id].append({
            'case_id': case_id,
            'reason': reason,
            'moderator': ctx.author.id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat()
        })
        infractions[member.id] += 1
        case_logs[case_id] = {
            'action': 'Warn',
            'target': member.id,
            'moderator': ctx.author.id,
            'reason': reason
        }
        await ctx.send(f"✅ {member.mention} has been warned. Case ID: {case_id} 📜")
        await notify_user(member, "warned", reason)
        await log_action("Warn", member, ctx.author, reason, f"Case ID: {case_id}, Infractions: {infractions[member.id]}")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in warn command", ctx.author, member, str(e))
warn.description = "Warns a user and logs the warning."
warn.usage = ".warn <user> [reason]"

@bot.command(name='mute')
@is_staff()
async def mute(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Mutes a user (assigns a 'Muted' role).
    Usage: .mute <user> [reason]
    """
    # **Enhancement**: Implement a proper 'Muted' role creation/assignment system.
    # For now, this is a placeholder. You'll need a 'Muted' role with no send message permissions.
    await ctx.send("This is a placeholder for the mute command. Please set up a 'Muted' role and implement the logic to assign it.")
    await log_action("Mute (Placeholder)", member, ctx.author, reason)
mute.description = "Mutes a user (requires a 'Muted' role setup)."
mute.usage = ".mute <user> [reason]"

@bot.command(name='tempmute')
@is_staff()
async def tempmute(ctx, member: discord.Member, duration_seconds: int, *, reason: str = "No reason provided"):
    """
    Temporarily mutes a user for a specified duration in seconds.
    Usage: .tempmute <user> <duration_seconds> [reason]
    """
    # **Enhancement**: Implement actual timed mute using discord.Member.timeout or custom role assignment/removal.
    await ctx.send(f"This is a placeholder for the temporary mute command for {duration_seconds} seconds.")
    await log_action("Tempmute (Placeholder)", member, ctx.author, reason, f"Duration: {duration_seconds}s")
tempmute.description = "Temporarily mutes a user."
tempmute.usage = ".tempmute <user> <duration_seconds> [reason]"


@bot.command(name='timeout')
@is_staff()
async def timeout_command(ctx, member: discord.Member, minutes: int, *, reason: str = "No reason provided"):
    """
    Timeouts a user using Discord's native timeout feature.
    Usage: .timeout <user> <minutes> [reason]
    """
    try:
        # Check for necessary permissions for the bot
        if not await check_bot_permissions(ctx, {'moderate_members': True}):
            return

        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await ctx.send(f"✅ {member.mention} has been timed out for {minutes} minutes! ⏰")
        await notify_user(member, "timed out", reason, duration.total_seconds())
        await log_action("Timeout", member, ctx.author, reason, f"Duration: {minutes} minutes")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to timeout this user! My role might be lower than theirs, or I lack 'Moderate Members' permission. 🛠️")
        await log_action("Permission Error: Timeout", member, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in timeout command", ctx.author, member, str(e))
timeout_command.description = "Times out a user for a specified duration."
timeout_command.usage = ".timeout <user> <minutes> [reason]"

@bot.command(name='kick')
@is_staff()
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Kicks a user from the guild.
    Usage: .kick <user> [reason]
    """
    try:
        if not await check_bot_permissions(ctx, {'kick_members': True}):
            return
        
        if ctx.author.top_role <= member.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("🚫 You cannot kick someone with an equal or higher role than yourself! 🌠")
            return

        await member.kick(reason=reason)
        await ctx.send(f"✅ {member.display_name} has been kicked from the galaxy! 🚀")
        await notify_user(member, "kicked", reason)
        await log_action("Kick", member, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to kick this user! My role might be lower than theirs, or I lack 'Kick Members' permission. 🛠️")
        await log_action("Permission Error: Kick", member, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in kick command", ctx.author, member, str(e))
kick.description = "Kicks a user from the server."
kick.usage = ".kick <user> [reason]"

@bot.command(name='ban')
@is_staff()
async def ban(ctx, user: discord.User, *, reason: str = "No reason provided"): # Use discord.User for potential out-of-guild bans
    """
    Bans a user from the guild.
    Usage: .ban <user_id_or_mention> [reason]
    """
    try:
        if not await check_bot_permissions(ctx, {'ban_members': True}):
            return
        
        # If the user is in the guild, check role hierarchy
        member = ctx.guild.get_member(user.id)
        if member and ctx.author.top_role <= member.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("🚫 You cannot ban someone with an equal or higher role than yourself! 🌠")
            return

        await ctx.guild.ban(user, reason=reason)
        await ctx.send(f"✅ {user.display_name} has been banned from the cosmic realm! 🌌")
        await notify_user(user, "banned", reason)
        await log_action("Ban", user, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to ban this user! My role might be lower than theirs, or I lack 'Ban Members' permission. 🛠️")
        await log_action("Permission Error: Ban", user, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in ban command", ctx.author, user, str(e))
ban.description = "Bans a user from the server."
ban.usage = ".ban <user_id_or_mention> [reason]"

@bot.command(name='tempban')
@is_staff()
async def tempban(ctx, user: discord.User, duration_seconds: int, *, reason: str = "No reason provided"):
    """
    Temporarily bans a user for a specified duration in seconds.
    Usage: .tempban <user_id_or_mention> <duration_seconds> [reason]
    """
    try:
        if not await check_bot_permissions(ctx, {'ban_members': True}):
            return
        
        member = ctx.guild.get_member(user.id)
        if member and ctx.author.top_role <= member.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("🚫 You cannot temporarily ban someone with an equal or higher role than yourself! 🌠")
            return

        await ctx.guild.ban(user, reason=f"Temporary ban: {reason} for {duration_seconds} seconds")
        await ctx.send(f"✅ {user.display_name} has been temporarily banned for {duration_seconds} seconds! ⏳")
        await notify_user(user, "temporarily banned", reason, duration_seconds)
        await log_action("Tempban", user, ctx.author, reason, f"Duration: {duration_seconds}s")

        await asyncio.sleep(duration_seconds)
        await ctx.guild.unban(user, reason=f"Temporary ban expired for {reason}")
        await ctx.send(f"🎉 {user.display_name} has been unbanned (tempban expired)! Welcome back to the galaxy! 🌌")
        await log_action("Unban (Tempban Expired)", user, bot.user, f"Tempban expired for {reason}")

    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to ban/unban this user! My role might be lower than theirs, or I lack 'Ban Members' permission. 🛠️")
        await log_action("Permission Error: Tempban", user, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in tempban command", ctx.author, user, str(e))
tempban.description = "Temporarily bans a user from the server."
tempban.usage = ".tempban <user_id_or_mention> <duration_seconds> [reason]"


@bot.command(name='softban')
@is_staff()
async def softban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Softbans a user (kicks and deletes messages from the last 7 days).
    Usage: .softban <user> [reason]
    """
    try:
        if not await check_bot_permissions(ctx, {'ban_members': True, 'kick_members': True}):
            return
        
        if ctx.author.top_role <= member.top_role and ctx.author.id != ctx.guild.owner_id:
            await ctx.send("🚫 You cannot softban someone with an equal or higher role than yourself! 🌠")
            return

        await member.ban(reason=reason, delete_message_days=7)
        await member.unban(reason="Softban: Rejoining allowed")
        await ctx.send(f"✅ {member.display_name} has been softbanned! Their recent messages (last 7 days) have been purged. 🧹")
        await notify_user(member, "softbanned", reason)
        await log_action("Softban", member, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to ban/unban this user! My role might be lower than theirs, or I lack 'Ban Members' permission. 🛠️")
        await log_action("Permission Error: Softban", member, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in softban command", ctx.author, member, str(e))
softban.description = "Softbans a user (kicks and deletes messages)."
softban.usage = ".softban <user> [reason]"


@bot.command(name='unban')
@is_staff()
async def unban(ctx, user_id: int, *, reason: str = "No reason provided"):
    """
    Unbans a user by their ID.
    Usage: .unban <user_id> [reason]
    """
    try:
        if not await check_bot_permissions(ctx, {'ban_members': True}):
            return

        user = await bot.fetch_user(user_id) # Fetch user by ID
        if not user:
            await ctx.send(f"⚠️ User with ID `{user_id}` not found! 🕳️")
            return

        # Check if the user is actually banned
        try:
            banned_users = [entry.user for entry in await ctx.guild.bans()]
            if user not in banned_users:
                await ctx.send(f"⚠️ User {user.mention} (ID: `{user_id}`) is not currently banned. 🚫")
                return
        except discord.Forbidden:
            await ctx.send("🚫 I don't have permission to view banned users. 🛠️")
            return
        
        await ctx.guild.unban(user, reason=reason)
        await ctx.send(f"🎉 {user.display_name} (ID: `{user_id}`) has been unbanned! Welcome back to the galaxy! 🌌")
        await log_action("Unban", user, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to unban this user! I lack 'Ban Members' permission. 🛠️")
        await log_action("Permission Error: Unban", user, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in unban command", ctx.author, user, str(e))
unban.description = "Unbans a user by their ID."
unban.usage = ".unban <user_id> [reason]"


@bot.command(name='slowmode')
@is_staff()
async def slowmode(ctx, channel: discord.TextChannel = None, seconds: int = 0):
    """
    Sets slowmode for a channel. Set to 0 to disable.
    Usage: .slowmode [channel] <seconds>
    """
    if channel is None:
        channel = ctx.channel # Default to current channel

    try:
        if not await check_bot_permissions(ctx, {'manage_channels': True}):
            return

        if seconds < 0 or seconds > 21600:
            await ctx.send("⚠️ Slowmode duration must be between 0 and 21600 seconds! ⏰")
            return

        await channel.edit(slowmode_delay=seconds)
        if seconds > 0:
            await ctx.send(f"✅ Slowmode set to {seconds} seconds in {channel.mention}! The cosmic pace has been adjusted! ⏳")
            await log_action("Slowmode Set", channel, ctx.author, f"{seconds} seconds")
        else:
            await ctx.send(f"✅ Slowmode disabled in {channel.mention}! The cosmic flow is back to normal! 💨")
            await log_action("Slowmode Disabled", channel, ctx.author, "Disabled")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to manage channels! I lack 'Manage Channels' permission. 🛠️")
        await log_action("Permission Error: Slowmode", channel, ctx.author, str(e), "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in slowmode command", ctx.author, channel, str(e))
slowmode.description = "Sets slowmode for a channel. Set to 0 to disable."
slowmode.usage = ".slowmode [channel] <seconds>"


@bot.command(name='lock')
@is_staff()
async def lock(ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
    """
    Locks a channel, preventing @everyone from sending messages.
    Usage: .lock [channel] [reason]
    """
    if channel is None:
        channel = ctx.channel

    try:
        if not await check_bot_permissions(ctx, {'manage_channels': True}):
            return

        # Deny send_messages for @everyone role
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        if overwrite.send_messages is False:
            await ctx.send(f"⚠️ {channel.mention} is already locked! 🔒")
            return
        
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
        await ctx.send(f"🔒 {channel.mention} has been locked! The cosmic gate is closed. 🚫")
        await log_action("Channel Locked", channel, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to manage channels! I lack 'Manage Channels' permission. 🛠️")
        await log_action("Permission Error: Lock", channel, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in lock command", ctx.author, channel, str(e))
lock.description = "Locks a channel, preventing @everyone from sending messages."
lock.usage = ".lock [channel] [reason]"


@bot.command(name='unlock')
@is_staff()
async def unlock(ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
    """
    Unlocks a channel, allowing @everyone to send messages.
    Usage: .unlock [channel] [reason]
    """
    if channel is None:
        channel = ctx.channel

    try:
        if not await check_bot_permissions(ctx, {'manage_channels': True}):
            return

        # Allow send_messages for @everyone role
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        if overwrite.send_messages is None or overwrite.send_messages is True:
            await ctx.send(f"⚠️ {channel.mention} is not locked! 🔓")
            return

        overwrite.send_messages = None # Remove explicit overwrite to revert to default permissions
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
        await ctx.send(f"🔓 {channel.mention} has been unlocked! The cosmic gate is open! 🎉")
        await log_action("Channel Unlocked", channel, ctx.author, reason)
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to manage channels! I lack 'Manage Channels' permission. 🛠️")
        await log_action("Permission Error: Unlock", channel, ctx.author, reason, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in unlock command", ctx.author, channel, str(e))
unlock.description = "Unlocks a channel, allowing @everyone to send messages."
unlock.usage = ".unlock [channel] [reason]"


@bot.command(name='purge', aliases=['clear'])
@is_staff()
async def purge(ctx, amount: int = 5):
    """
    Deletes a specified number of messages from the current channel.
    Usage: .purge [amount=5]
    """
    if amount <= 0:
        await ctx.send("⚠️ Please provide a positive number of messages to purge! 🔢")
        return
    if amount > 100: # Discord API limit for bulk delete
        await ctx.send("⚠️ I can only purge up to 100 messages at a time! For larger purges, run the command multiple times. 🔄")
        amount = 100

    try:
        if not await check_bot_permissions(ctx, {'manage_messages': True, 'read_message_history': True}):
            return

        # Add 1 to amount to include the command message itself
        deleted = await ctx.channel.purge(limit=amount + 1) 
        await ctx.send(f"✅ Purged {len(deleted) - 1} cosmic messages from this channel! 🧹", delete_after=5) # -1 because of the command message
        await log_action("Purge", ctx.channel, ctx.author, f"Purged {len(deleted) - 1} messages", f"Channel: {ctx.channel.name}")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to manage messages in this channel! I lack 'Manage Messages' or 'Read Message History' permission. 🛠️")
        await log_action("Permission Error: Purge", ctx.channel, ctx.author, "Bot lacks permissions")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in purge command", ctx.author, ctx.channel, str(e))
purge.description = "Deletes a specified number of messages."
purge.usage = ".purge [amount]"


@bot.command(name='profile')
async def profile(ctx, member: discord.Member = None):
    """
    Displays the reputation and infraction profile of a user.
    Usage: .profile [user]
    """
    if member is None:
        member = ctx.author

    rep = reputation[member.id]
    user_warnings = warnings[member.id]
    infraction_count = infractions[member.id]

    embed = discord.Embed(
        title=f"👤 Cosmic Profile: {member.display_name} 🌠",
        color=discord.Color.blue(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )
    embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
    embed.add_field(name="🌟 Reputation Points", value=f"{rep}", inline=True)
    embed.add_field(name="🚨 Total Infractions", value=f"{infraction_count}", inline=True)

    if user_warnings:
        warn_details = []
        for warn_entry in user_warnings:
            moderator = await bot.fetch_user(warn_entry['moderator'])
            warn_details.append(f"**Case ID**: {warn_entry['case_id']}\n"
                                f"**Reason**: {warn_entry['reason']}\n"
                                f"**Moderator**: {moderator.mention if moderator else 'Unknown'}\n"
                                f"**Timestamp**: {datetime.datetime.fromisoformat(warn_entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        embed.add_field(name="📜 Warnings", value="\n\n".join(warn_details), inline=False)
    else:
        embed.add_field(name="📜 Warnings", value="No warnings recorded.", inline=False)
    
    await ctx.send(embed=embed)
profile.description = "Displays the reputation and infraction profile of a user."
profile.usage = ".profile [user]"


@bot.command(name='report')
async def report(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """
    Reports a user to the moderation team.
    Usage: .report <user> [reason]
    """
    mod_log_channel = bot.get_channel(MOD_LOG_CHANNEL_ID)
    if not mod_log_channel:
        await ctx.send("⚠️ Moderation log channel not found! Cannot report. 🕳️")
        return
    
    try:
        report_embed = discord.Embed(
            title="🚨 User Report Filed! 🚨",
            description=f"**Reported User:** {member.mention}\n**Reported By:** {ctx.author.mention}\n**Reason:** {reason}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        report_embed.set_footer(text=f"Reported in #{ctx.channel.name}")
        await mod_log_channel.send(embed=report_embed)
        await ctx.send(f"✅ {member.mention} has been reported to the cosmic authorities! We'll investigate! 🕵️‍♀️")
        await log_action("User Report", member, ctx.author, reason, f"Reported by: {ctx.author.display_name}")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to send messages in the moderation log channel. 🛠️")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in report command", ctx.author, member, str(e))
report.description = "Reports a user to the moderation team."
report.usage = ".report <user> [reason]"


# @bot.command(name='verify')
# async def verify(ctx):
#     """
#     Initiates the verification process for a user.
#     Usage: .verify
#     """
#     # This is a placeholder for a more robust verification system.
#     # A real verification system would involve:
#     # 1. Sending a DM with instructions/a link to a verification portal.
#     # 2. Checking if the user meets certain criteria (e.g., passing a quiz, agreeing to rules).
#     # 3. Assigning a 'Verified' role and removing any 'Unverified' role.
#     await ctx.send("This is a placeholder for the verification command. A full verification system is a complex enhancement.")
#     await log_action("Verify (Placeholder)", ctx.author, None, "User initiated verification")
# verify.description = "Initiates the verification process."
# verify.usage = ".verify"

@bot.command(name='modmailclose')
@is_staff()
async def modmail_close(ctx, ticket_id: str = None):
    """
    Closes an open modmail ticket.
    Usage: .modmailclose [ticket_id]
    """
    if isinstance(ctx.channel, discord.Thread) and ctx.channel.parent_id == MODMAIL_CHANNEL_ID:
        # If command is used within a modmail thread, try to find the ticket_id automatically
        for tid, ticket_data in modmail_tickets.items():
            if ticket_data['thread_id'] == ctx.channel.id:
                ticket_id = tid
                break
        if not ticket_id:
            await ctx.send("⚠️ This doesn't seem to be an active modmail ticket thread. Please provide a ticket ID.")
            return

    if not ticket_id or ticket_id not in modmail_tickets:
        await ctx.send(f"⚠️ Modmail ticket `{ticket_id}` not found or invalid! 🕳️")
        return

    ticket = modmail_tickets[ticket_id]
    if ticket['status'] == 'closed':
        await ctx.send(f"⚠️ Ticket `{ticket_id}` is already closed! 🔒")
        return

    try:
        user_id = int(ticket['user_id'])
        user = await bot.fetch_user(user_id) # Fetch user
        thread = discord.utils.get(ctx.guild.threads, id=ticket['thread_id'])
        
        ticket['status'] = 'closed'
        # Log and notify
        await ctx.send(f"✅ Modmail ticket `{ticket_id}` closed! 🔒")
        if user:
            try:
                await user.send(f"🔒 Your modmail ticket `{ticket_id}` has been closed by {ctx.author.mention}. If you need further assistance, open a new ticket with `.modmail`!")
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user.id} about modmail closure.")
        if thread:
            try:
                await thread.edit(locked=True, archived=True, reason=f"Modmail ticket {ticket_id} closed by {ctx.author.name}")
                await thread.send(f"🔒 This modmail ticket has been closed by {ctx.author.mention}. It is now archived.")
            except discord.Forbidden:
                logger.error(f"Bot lacks permissions to lock/archive thread {thread.id}")
        await log_action("Modmail Close", user, ctx.author, f"Ticket #{ticket_id} closed")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in modmail_close command", ctx.author, None, str(e))
modmail_close.description = "Closes an open modmail ticket."
modmail_close.usage = ".modmailclose [ticket_id]"


@bot.command(name='modmailopen')
@is_staff()
async def modmail_open(ctx, ticket_id: str):
    """
    Reopens a closed modmail ticket.
    Usage: .modmailopen <ticket_id>
    """
    if ticket_id not in modmail_tickets:
        await ctx.send(f"⚠️ Modmail ticket `{ticket_id}` not found! 🕳️")
        return

    ticket = modmail_tickets[ticket_id]
    if ticket['status'] == 'open':
        await ctx.send(f"⚠️ Ticket `{ticket_id}` is already open! 🔓")
        return

    try:
        user_id = int(ticket['user_id'])
        user = await bot.fetch_user(user_id) # Fetch user
        thread = discord.utils.get(ctx.guild.threads, id=ticket['thread_id'])

        if not thread:
            # Attempt to fetch thread if not in cache (e.g., bot restarted)
            try:
                thread = await ctx.guild.fetch_channel(ticket['thread_id'])
            except discord.NotFound:
                await ctx.send(f"⚠️ Associated thread for ticket `{ticket_id}` not found! Cannot reopen. 🕳️")
                await log_action("Modmail Open Failed (Thread Missing)", user, ctx.author, f"Ticket #{ticket_id} thread missing")
                return
            except discord.Forbidden:
                await ctx.send(f"🚫 I don't have permission to fetch the thread for ticket `{ticket_id}`. 🛠️")
                await log_action("Modmail Open Failed (Thread Fetch Forbidden)", user, ctx.author, f"Ticket #{ticket_id} thread fetch forbidden")
                return

        ticket['status'] = 'open'
        # Unarchive and unlock the thread
        await thread.edit(locked=False, archived=False, reason=f"Modmail ticket {ticket_id} reopened by {ctx.author.name}")
        await ctx.send(f"✅ Modmail ticket `{ticket_id}` reopened! 🔓")
        if user:
            try:
                await user.send(f"🔓 Your modmail ticket `{ticket_id}` has been reopened by {ctx.author.mention}. You can now send messages again.")
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user.id} about modmail reopening.")
        
        await thread.send(f"🔓 This modmail ticket has been reopened by {ctx.author.mention}.")
        await log_action("Modmail Open", user, ctx.author, f"Ticket #{ticket_id} reopened")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in modmail_open command", ctx.author, None, str(e))
modmail_open.description = "Reopens a closed modmail ticket."
modmail_open.usage = ".modmailopen <ticket_id>"

# --- Status Commands ---
@bot.command(name='free', aliases=['f'])
async def set_status_free(ctx):
    """Set your status to 'Free ✅'."""
    user_statuses[ctx.author.id] = "Free ✅"
    await ctx.send("✅ Your status has been set to `Free ✅`! Ready to shine! ✨")
    await update_status_board()
set_status_free.description = "Set your status to 'Free ✅'."
set_status_free.usage = ".free"

@bot.command(name='sleeping', aliases=['s'])
async def set_status_sleeping(ctx):
    """Set your status to 'Sleeping 😴'."""
    user_statuses[ctx.author.id] = "Sleeping 😴"
    await ctx.send("😴 Your status has been set to `Sleeping 😴`! Sweet dreams! 🌙")
    await update_status_board()
set_status_sleeping.description = "Set your status to 'Sleeping 😴'."
set_status_sleeping.usage = ".sleeping"

@bot.command(name='dolater', aliases=['d'])
async def set_status_dolater(ctx):
    """Set your status to 'Do Later 🚧'."""
    user_statuses[ctx.author.id] = "Do Later 🚧"
    await ctx.send("🚧 Your status has been set to `Do Later 🚧`! On a cosmic mission! 🪐")
    await update_status_board()
set_status_dolater.description = "Set your status to 'Do Later 🚧'."
set_status_dolater.usage = ".dolater"

@bot.command(name='studying', aliases=['st'])
async def set_status_studying(ctx):
    """Set your status to 'Studying 📚'."""
    user_statuses[ctx.author.id] = "Studying 📚"
    await ctx.send("📚 Your status has been set to `Studying 📚`! Dive into knowledge! 🧠")
    await update_status_board()
set_status_studying.description = "Set your status to 'Studying 📚'."
set_status_studying.usage = ".studying"

@bot.command(name='outside', aliases=['o'])
async def set_status_outside(ctx):
    """Set your status to 'Outside 🚶‍♂️'."""
    user_statuses[ctx.author.id] = "Outside 🚶‍♂️"
    await ctx.send("🚶‍♂️ Your status has been set to `Outside 🚶‍♂️`! Stargazing IRL! 🍃")
    await update_status_board()
set_status_outside.description = "Set your status to 'Outside 🚶‍♂️'."
set_status_outside.usage = ".outside"

@bot.command(name='break', aliases=['b'])
async def set_status_break(ctx):
    """Set your status to 'On Break ☕'."""
    user_statuses[ctx.author.id] = "On Break ☕"
    await ctx.send("☕ Your status has been set to `On Break ☕`! Chilling in a nebula lounge! 🛋️")
    await update_status_board()
set_status_break.description = "Set your status to 'On Break ☕'."
set_status_break.usage = ".break"

@bot.command(name='clearstatus')
async def clear_status(ctx):
    """Clear your current status."""
    if ctx.author.id in user_statuses:
        del user_statuses[ctx.author.id]
        await ctx.send("❌ Your cosmic status has been cleared! 🌌")
        await update_status_board()
    else:
        await ctx.send("ℹ️ You don't have a status set to clear. 🤷‍♀️")
clear_status.description = "Clear your current status."
clear_status.usage = ".clearstatus"

# --- Other Commands ---
@bot.command(name='suggest')
async def suggest(ctx, *, suggestion_text: str):
    """
    Submit a suggestion for the server.
    Usage: .suggest <your suggestion>
    """
    suggestion_channel = bot.get_channel(SUGGESTION_CHANNEL_ID)
    suggestion_category = bot.get_channel(SUGGESTION_CATEGORY_ID)

    if not suggestion_channel:
        await ctx.send(f"⚠️ Suggestion channel with ID {SUGGESTION_CHANNEL_ID} not found! Please inform staff. 🕳️")
        return
    if not suggestion_category:
        await ctx.send(f"⚠️ Suggestion discussion category with ID {SUGGESTION_CATEGORY_ID} not found! Please inform staff. 🕳️")
        return

    try:
        global case_id_counter # Reusing case_id_counter for suggestions for simplicity
        suggestion_id = case_id_counter
        case_id_counter += 1

        embed = discord.Embed(
            title=f"💡 New Cosmic Suggestion #{suggestion_id} 🌟",
            description=suggestion_text,
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        embed.set_footer(text="React with ✅ to approve, ❌ to disapprove.")

        suggestion_message = await suggestion_channel.send(embed=embed)
        await suggestion_message.add_reaction("✅")
        await suggestion_message.add_reaction("❌")

        suggestions.append({
            'id': suggestion_id,
            'text': suggestion_text,
            'author_id': ctx.author.id,
            'message_id': suggestion_message.id,
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'status': 'pending'
        })
        
        # Create a private thread for discussion (optional, based on SUGGESTION_CATEGORY_ID usage)
        if suggestion_category:
            try:
                # Create a thread under the suggestion channel, but put it in the category
                # Note: Threads cannot directly be created in categories, they are created in channels.
                # If SUGGESTION_CATEGORY_ID is meant for private discussion, the channel must be within that category.
                # A common approach is to create a thread from the suggestion message.
                discussion_thread = await suggestion_message.create_thread(
                    name=f"Suggestion-#{suggestion_id}-Discussion",
                    auto_archive_duration=1440 # 24 hours
                )
                await discussion_thread.send(f"This is a private discussion thread for suggestion #{suggestion_id}. Staff can discuss here.")
                logger.info(f"Created discussion thread for suggestion #{suggestion_id}")
            except discord.Forbidden:
                logger.warning(f"Bot lacks permissions to create thread for suggestion in channel {suggestion_channel.id}. Check 'create_private_threads' or 'create_public_threads'.")
            except Exception as e:
                logger.error(f"Error creating discussion thread for suggestion: {e}")

        await ctx.send(f"✅ Your cosmic suggestion #{suggestion_id} has been submitted! Thank you for helping shape our galaxy! 🌟")
        await log_action("Suggestion Submitted", ctx.author, None, f"Suggestion #{suggestion_id}: {suggestion_text}")
    except discord.Forbidden:
        await ctx.send("🚫 I don't have permission to send messages or add reactions in the suggestion channel. 🛠️")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in suggest command", ctx.author, None, str(e))
suggest.description = "Submit a suggestion for the server."
suggest.usage = ".suggest <your suggestion>"


@bot.command(name='link')
@is_staff()
async def add_link(ctx, trigger: str, notes_name: str, file_link: str):
    """
    Adds a custom link to the bot's memory for quick sharing.
    Usage: .link <trigger_word> <notes_name> <file_link>
    """
    links.append({'trigger': trigger.lower(), 'notes_name': notes_name, 'file_link': file_link, 'user': ctx.author.id, 'channel': ctx.channel.id})
    await ctx.send(f"📚 Here's your requested link: '{trigger}' added for '{notes_name}'! 📎")
    await log_action("Link Added", ctx.author, None, f"Trigger: {trigger}, Notes: {notes_name}, Link: {file_link}")
add_link.description = "Adds a custom link for quick sharing."
add_link.usage = ".link <trigger_word> <notes_name> <file_link>"

@bot.command(name='listlink')
async def list_links(ctx):
    """
    Lists all custom links stored in the bot's memory.
    Usage: .listlink
    """
    if not links:
        await ctx.send("🌌 No cosmic links have been added yet! Use `.link` to add some. 📎")
        return

    embed = discord.Embed(
        title="📎 Cosmic Links Library 📎",
        description="Here are all the custom links registered!",
        color=discord.Color.teal(),
        timestamp=datetime.datetime.now(datetime.timezone.utc)
    )

    for idx, link_data in enumerate(links):
        user = bot.get_user(link_data['user'])
        embed.add_field(
            name=f"Link #{idx+1}: {link_data['trigger']}",
            value=f"**Notes:** [{link_data['notes_name']}]({link_data['file_link']})\n**Added by:** {user.mention if user else 'Unknown User'}",
            inline=False
        )
    await ctx.send(embed=embed)
list_links.description = "Lists all custom links."
list_links.usage = ".listlink"

@bot.command(name='rallcmd')
@commands.is_owner() # Only bot owner can run this command
async def reload_all_commands(ctx):
    """
    Reloads all commands (useful during development for hot-reloading).
    Usage: .rallcmd
    """
    await ctx.send("🔄 Initiating cosmic command reload... please stand by! 🚀")
    try:
        # This requires commands to be in cogs or a specific structure
        # For this example, assuming commands are directly in this file for simplicity,
        # but in a larger bot, you would reload cogs.
        # This specific command might not reload all changes without a full bot restart
        # if new commands are not dynamically added.
        await ctx.send("✅ All commands reloaded (conceptual)! For code changes, a bot restart might be needed. ✨")
        await log_action("Reload All Commands", ctx.author, None, "Attempted to reload all commands")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit during reload: {str(e)}. 🚖")
        await log_action("Error Reloading Commands", ctx.author, None, str(e))
reload_all_commands.description = "Reloads all bot commands."
reload_all_commands.usage = ".rallcmd"

@bot.command(name='sync')
@commands.is_owner() # Only bot owner can run this command
async def sync_commands(ctx):
    """
    Syncs slash commands to Discord.
    Usage: .sync
    """
    await ctx.send("🔄 Syncing cosmic slash commands... this might take a moment! 🌌")
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(synced)} slash commands! They are now shining brightly! 🌟")
        await log_action("Sync Commands", ctx.author, None, f"Synced {len(synced)} slash commands")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit during sync: {str(e)}. Try again! 🚖")
        await log_action("Error Syncing Commands", ctx.author, None, str(e))
sync_commands.description = "Syncs slash commands to Discord."
sync_commands.usage = ".sync"

@bot.command(name='guide')
async def show_guide(ctx):
    """
    Directs users to the guide channel.
    Usage: .guide
    """
    guide_channel = bot.get_channel(GUIDE_CHANNEL_ID)
    if guide_channel:
        await ctx.send(f"📖 Explore our galaxy's knowledge! Head over to the {guide_channel.mention} channel for guides and resources! 📚")
    else:
        await ctx.send(f"⚠️ Guide channel with ID {GUIDE_CHANNEL_ID} not found! Please inform staff. 🕳️")
show_guide.description = "Directs users to the guide channel."
show_guide.usage = ".guide"

@bot.command(name='ping')
async def ping(ctx):
    """
    Checks the bot's latency.
    Usage: .ping
    """
    await ctx.send(f"🛰️ Pong! My cosmic latency is {round(bot.latency * 1000)}ms! 📡")
ping.description = "Checks the bot's latency."
ping.usage = ".ping"

@bot.command(name='say')
@is_staff()
async def say_command(ctx, *, message: str):
    """
    Make the bot say something (Staff only).
    Usage: .say <message>
    """
    try:
        await ctx.send(message)
        await log_action("Bot Say", ctx.author, None, f"Bot said: {message}")
    except Exception as e:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(e)}. Try again! 🚖")
        await log_action("Error in say_command", ctx.author, None, str(e))
say_command.description = "Make the bot say something (Staff only)."
say_command.usage = ".say <message>"

# --- Slash Commands (New Enhancement) ---
# Example of a simple slash command
@bot.tree.command(name="hello", description="Say hello to the bot!")
async def hello_slash(interaction: discord.Interaction):
    """
    Says hello to the user who invoked the slash command.
    """
    await interaction.response.send_message(f"Greetings, {interaction.user.mention}! May your journey through the cosmos be filled with wonder! 🌟")
    await log_action("Slash Command Used", interaction.user, None, "/hello command")

# --- Error Handling ---
@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for commands.
    """
    if isinstance(error, commands.MissingPermissions) or isinstance(error, commands.CheckFailure):
        await ctx.send("🚫 You don’t have the cosmic powers to use this command! 🌠")
    elif isinstance(error, commands.MissingRequiredArgument):
        # Improved error message with command usage
        await ctx.send(f"⚠️ Missing arguments! Usage: `{ctx.command.usage}` 🌌")
    elif isinstance(error, commands.BadArgument):
        # Improved error message with command usage
        await ctx.send(f"⚠️ Invalid arguments! Usage: `{ctx.command.usage}` 🌌")
    elif isinstance(error, commands.CommandNotFound):
        # Silently ignore if command not found to avoid spamming
        pass
    else:
        await ctx.send(f"⚠️ A cosmic storm hit: {str(error)}. Try again or contact support! 🚖")
        logger.error(f"Command Error in {ctx.command}: {str(error)}")
        # Log the error for debugging
        await log_action("Command Error", ctx.author, None, f"Command: {ctx.command}, Error: {str(error)}")
    logger.error(f"Command error in {ctx.command}: {str(error)}")

# --- Run the Bot ---
if __name__ == "__main__":
    try:
        # Run the bot with the loaded token
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid DISCORD_TOKEN! Your bot cannot launch into the cosmos. 🚫")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An unexpected error occurred during bot startup: {str(e)}")
        sys.exit(1)