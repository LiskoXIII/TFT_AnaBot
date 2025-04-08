import os
import logging
import argparse

import discord
from discord import Reaction, Member, User, Message
from discord.ext import commands

from riot_api import RiotAPI
import envs

envs.set_envs()

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize the bot with the correct intents
intents = discord.Intents.default()
intents.reactions = True  # Enable Reactions Intent
intents.message_content = True  # Enable Message Content Intent
BOT: commands.Bot = commands.Bot(command_prefix="!", intents=intents)

global MAN_MSG
MAN_MSG: dict[int, dict[str, list[str] | str, int]] = {}  # Dictionary to hold message IDs and their corresponding data
RIOT_API: RiotAPI = None

def initialize_shared_state(shared_dict):
    """
    Initializes a shared state by assigning the provided dictionary to a global variable.

    Args:
        shared_dict (dict): A dictionary to be shared across different parts of the program.
    """
    global MAN_MSG
    MAN_MSG = shared_dict

def generate_embed(page, pages, summoner):
    """
    Generates a Discord embed object for displaying analysis information.

    Args:
        page (int): The current page index (0-based) to display.
        pages (list of str): A list of strings where each string represents the content of a page.
        summoner (str): The name of the summoner for whom the analysis is being generated.

    Returns:
        discord.Embed: A Discord embed object containing the analysis information for the specified page.
    """
    return discord.Embed(
        title=f"{summoner} Analysis (Page {page + 1}/{len(pages)})",
        description=pages[page],
        color=discord.Color.blue()
    )

@BOT.event
@commands.has_permissions(manage_messages=True) # Check if the bot has the permission
@commands.bot_has_permissions(manage_messages=True) # Check if the bot has the permission
async def on_reaction_add(reaction: Reaction, user: Member | User):
    """
    Handles the addition of reactions to a message and updates the message content
    based on the reaction. This function is specifically designed to handle pagination
    reactions (⬅️ and ➡️) for a message containing multiple pages of content.
    Args:
        reaction (Reaction): The reaction object that was added to the message.
        user (Member | User): The user who added the reaction.
    Behavior:
        - If the reaction is either ⬅️ or ➡️ and the message ID is tracked in the global
          MAN_MSG dictionary, the function updates the current page of the message.
        - ⬅️ decreases the current page index if it is greater than 0.
        - ➡️ increases the current page index if it is less than the total number of pages - 1.
        - The message content is updated with the new page using the `generate_embed` function.
        - The user's reaction is removed after processing.
        - The current page index is updated in the MAN_MSG dictionary.
    Global Variables:
        MAN_MSG (dict): A global dictionary that tracks paginated messages. Each entry contains:
            - 'cp': The current page index.
            - 'p': The list of pages (content).
            - 's': The summoner or associated data for the message.
    Notes:
        - The function ensures that the bot does not respond to its own reactions.
        - The function assumes the presence of a global `BOT` object representing the bot client.
    """
    global MAN_MSG
    if reaction.message.id in MAN_MSG and user != BOT.user and reaction.emoji in ["⬅️", "➡️"]:
        current_page = MAN_MSG[reaction.message.id]['cp']
        pages = MAN_MSG[reaction.message.id]['p']
        summoner = MAN_MSG[reaction.message.id]['s']
        total_pages = len(pages)
        if str(reaction.emoji) == "⬅️" and current_page > 0:
            current_page -= 1
            await reaction.message.edit(embed=generate_embed(current_page, pages, summoner))
        elif str(reaction.emoji) == "➡️" and current_page < total_pages - 1:
            current_page += 1
            await reaction.message.edit(embed=generate_embed(current_page, pages, summoner))

        # Remove the user's reaction after processing
        await reaction.message.remove_reaction(reaction.emoji, user)

        MAN_MSG[reaction.message.id] = {"p":pages, "cp": current_page, "s": summoner}  # Update current page in the dictionary
        logging.info(f"MAN_MSG updated: {MAN_MSG[reaction.message.id]["cp"]}")


# Helper function to send a long message in pages (each page dedicated to a player)
async def send_analysis_pages(ctx, analysis_data, summoner_name):
    """
    Sends a paginated analysis report as an embedded message to the Discord channel.
    This function sends an initial embed message containing analysis data for a summoner
    and sets up navigation reactions for users to browse through multiple pages of data.
    Args:
        ctx (commands.Context): The context of the command invocation, which includes
            information about the channel, author, and guild.
        analysis_data (list): A list of analysis data, where each entry corresponds to
            a player's data to be displayed on a separate page.
        summoner_name (str): The name of the summoner for whom the analysis is being generated.
    Side Effects:
        - Sends an embed message to the Discord channel.
        - Adds reaction emojis ("⬅️" and "➡️") to the message for navigation.
        - Updates the global `MAN_MSG` dictionary to track the message ID, analysis data,
          current page index, and summoner name.
    Note:
        This function assumes the existence of a `generate_embed` function to create
        the embed for each page and a global `MAN_MSG` dictionary for managing state.
    """
    # Calculate number of pages required (each page will hold 1 player's data)
    message: Message = await ctx.send(embed=generate_embed(0, analysis_data, summoner_name))

    # Add reaction emojis for navigation
    await message.add_reaction("⬅️")  # Left arrow (previous)
    await message.add_reaction("➡️")  # Right arrow (next)

    global MAN_MSG
    MAN_MSG[message.id] = {"p":analysis_data, "cp": 0, "s": summoner_name}


# Command to analyze a player's most recent game
@BOT.command(name="analyze", help="Analyze a player's most recent TFT game")
async def analyze(ctx, summoner_name):
    """
    Analyzes the most recent Teamfight Tactics (TFT) match for a given summoner.
    This function fetches summoner data, retrieves their match history, analyzes the most recent match,
    and sends the analysis results as paginated messages in the Discord channel.
    Args:
        ctx (commands.Context): The context of the command invocation, used to interact with Discord.
        summoner_name (str): The name of the summoner to analyze.
    Returns:
        None: This function sends messages to the Discord channel and does not return any value.
    Raises:
        None: Any exceptions are handled internally, and appropriate error messages are sent to the Discord channel.
    Behavior:
        - Displays a loading message while fetching data.
        - Retrieves summoner data using the Riot API.
        - Handles errors if the summoner is not found or if required data (e.g., puuid) is missing.
        - Fetches the summoner's match history and analyzes the most recent match.
        - Deletes the loading message once data is fetched and analyzed.
        - Sends the analysis results as paginated messages to the Discord channel.
    """
    # Show loading message
    loading_message: Message = await ctx.send("Fetching data... Please wait.")

    # Fetch summoner data
    summoner_data = await RIOT_API.get_summoner_data(summoner_name)

    if not summoner_data:
        embed = discord.Embed(
            title="Error",
            description=f"Could not find summoner **{summoner_name}**. Please check the name and try again.",
            color=discord.Color.red()
        )
        await loading_message.edit(content="Error occurred.", embed=embed)
        return

    # Get puuid from summoner data
    puuid = summoner_data.get('puuid')
    if not puuid:
        embed = discord.Embed(
            title="Error",
            description=f"Could not retrieve the puuid for summoner **{summoner_name}**.",
            color=discord.Color.red()
        )
        await loading_message.edit(content="Error occurred.", embed=embed)
        return

    # Fetch match history using the puuid
    match_history = await RIOT_API.get_tft_match_history(puuid)

    if not match_history:
        embed = discord.Embed(
            title="Error",
            description=f"Could not fetch match history for **{summoner_name}**.",
            color=discord.Color.red()
        )
        await loading_message.edit(content="Error occurred.", embed=embed)
        return

    match_id = match_history[0]

    # Analyze the most recent match
    analysis = await RIOT_API.analyze_tft_game(match_id)

    # Delete the loading message now that we have the data
    await loading_message.delete()

    # Send the analysis pages
    await send_analysis_pages(ctx, analysis, summoner_name)


def run(riot_key, discord_token):
    """
    Initializes the Riot API with the provided key and starts the Discord bot.
    Args:
        riot_key (str): The API key for accessing Riot Games' API.
        discord_token (str): The token for authenticating the Discord bot.
    Raises:
        discord.HTTPException: If an HTTP error occurs while running the Discord bot.
            Specifically logs an error if the status code is 429 (Too Many Requests).
    """
    global RIOT_API
    RIOT_API = RiotAPI(riot_key)

    try:
        BOT.run(discord_token)
    except discord.HTTPException as e:
        if e.status == 429:
            logging.error("The servers denied the connection due to too many requests.")
        else:
            raise e

def main():
    parser = argparse.ArgumentParser(description="TFT Bot")
    parser.add_argument("--riot-api-key", help="Riot API Key")
    parser.add_argument("--discord-token", help="Discord Bot Token")
    args = parser.parse_args()

    envs.set_envs()

    RIOT_API_KEY = args.riot_api_key or os.getenv("RIOT_API_KEY")
    DISCORD_TOKEN = args.discord_token or os.getenv("DISCORD_TOKEN")

    # Initialize logging
    logging.basicConfig(level=logging.INFO)

    if not RIOT_API_KEY or not DISCORD_TOKEN:
        raise ValueError("Riot API Key and Discord Token must be provided either as arguments or environment variables.")

    run(RIOT_API_KEY, DISCORD_TOKEN)

# Run the bot
if __name__ == "__main__":
    main()