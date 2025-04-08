import os

def set_envs():
    os.environ["DISCORD_TOKEN"] = "FILL_ME" if os.environ.get("DISCORD_TOKEN") is None else os.environ["DISCORD_TOKEN"]
    os.environ["RIOT_API_KEY"] = "FILL_ME" if os.environ.get("RIOT_API_KEY") is None else os.environ["RIOT_API_KEY"]
    os.environ["DISCORD_USER"] = "FILL_ME" if os.environ.get("DISCORD_USER") is None else os.environ["DISCORD_USER"]
    os.environ["DISCORD_PW"] = "FILL_ME" if os.environ.get("DISCORD_PW") is None else os.environ["DISCORD_PW"]