"""
Main script for Witness: Social Deducation Word Game

Runs the Discord bot client and handles user messages and reactions.
"""

import discord
import os
from dotenv import load_dotenv
from gameplay import Game

MAX_GAMES = 3
MAX_PLAYERS = 12

# Discord client settings
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
client = discord.Client(intents=intents)

# List of ongoing Witness games
game_list = []

@client.event
async def on_ready():
    '''
    Actions in response to logging in.
    '''
    print('DISCORD BOT logged in as {0.user}.'.format(client))

@client.event
async def on_message(message):
    '''
    Actions in response to a user message.
    '''
    # Ignore messages sent by self
    if message.author.id == client.user.id:
        return

    # Response to $hello with "Hello!"
    if message.content == "$hello":
        await message.channel.send("Hello!")
        return

    # Start new Witness game on $play
    if message.content == "$play":
        if len(game_list) < MAX_GAMES:
            game_list.append(await Game.initialize(message))
        else:
            await message.channel.send(f"Cannot create a new game. There are already ongoing {MAX_GAMES} games.")
        return
    
    # Clean up existing Witness categories and channels on $prune
    if message.content == "$prune":
        for category in message.guild.categories:
            if category.name.startswith("Witness-"):
                for channel in category.channels:
                    await channel.delete()  
                await category.delete()
        return

    # Find the game associated with the message and let the Game handle the message
    for game in game_list:
        if message.channel.category.id == game.category.id:
            await game.handle_message(message)
            return

@client.event
async def on_reaction_add(reaction, user):
    '''
    Actions in response to a message reaction
    '''
    # Ignore reactions made by self
    if user == client.user.id:
        return

    # If a user reacts to a game registration message, then add the user as a player in that game
    for game in game_list:
        if reaction.message.id == game.registration_msg.id:
            if user not in [player.user for player in game.player_list]:
                if len(game.player_list) < MAX_PLAYERS:
                    await game.add_player(user)
                    return
            
# Take environment variables from .env   
load_dotenv()

# Run discord client
client.run(os.getenv('DISCORD_TOKEN'))