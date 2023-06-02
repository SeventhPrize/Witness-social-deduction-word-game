import discord
import os
import asyncio
import random
from dotenv import load_dotenv

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)

game_list = []

@client.event
async def on_ready():
    print('DISCORD BOT logged in as {0.user}.'.format(client))

@client.event
async def on_message(message):
    if message.author is client.user:
        return

    if message.content == "$hello":
        await message.channel.send("Hello!")
        return

    if message.content == "$play":
        category = await message.guild.create_category("Witness-" + str(random.randint(1000, 9999)))
        registration_msg = await message.channel.send(f"React to this message to play Witness: Social Deduction Word Game. After reacting, check category `{category}` for your private channel.")
        new_game = await Game.initialize(category, registration_msg, message.author)
        game_list.append(new_game)
        return
    
    for game in game_list:
        if message.channel.category is game.category:
            await game.handle_message(message)
            return

@client.event
async def on_reaction_add(reaction, user):
    for game in game_list:
        if reaction.message.id == game.registration_msg.id:
            if user not in [player.user for player in game.player_list]:
                await game.add_player(user)
                return
            
class Game:
    category = None
    registration_msg = None
    player_list = None
    villain_count = None
    gamestate = None

    async def initialize(category, registration_msg, creator):
        self = Game()
        self.category = category
        self.registration_msg = registration_msg
        self.player_list = []
        self.villain_count = 1
        self.gamestate = "Creation"
        await self.add_player(creator)
        await self.send_game_creator_message()
        return self

    async def add_player(self, user):
        player = await Player.initialize(user, self.category)
        self.player_list.append(player)
        return player
    
    async def send_game_creator_message(self):
        await self.player_list[0].send_message("[CREATION MENU HERE]")
        return

    async def handle_message(self, message):
        pass

class Player:
    user = None
    category = None
    channel = None
    role = None

    async def initialize(user, category):
        self = Player()
        self.user = user
        self.category = category
        self.role = None
        self.channel = await self.create_private_channel(user)
        await self.send_message("[RULES HERE]")
        return self

    async def create_private_channel(self, user):
        overwrites = {
            self.category.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True),
            self.category.guild.me: discord.PermissionOverwrite(view_channel=True)
        }
        channel = await self.category.create_text_channel(user.name, overwrites=overwrites)
        return channel
    
    async def send_message(self, content):
        await self.channel.send(content) 
        return

class GameState:
    
    game = None

    async def initialize(game):
        self = GameState()
        self.game = game
        return self

    async def handle_message(self, message):
        pass


class GameStateCreation(GameState):

    # TODO visitor framework implementation to handle messages

load_dotenv()  # take environment variables from .env.
client.run(os.getenv('DISCORD_TOKEN'))