import logging
import asyncio

import aiohttp

class RiotAPI():

    def __init__(self, api_key):
        self.api_key = api_key
        self.headers = {'X-Riot-Token': self.api_key}

    # Helper function to get data from the API with retry logic
    async def get_api_data(self, url, retries=5, backoff_factor=1.5):
        async with aiohttp.ClientSession() as session:
            attempt = 0
            while attempt < retries:
                try:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status == 429:  # Too many requests
                            retry_after = response.headers.get('Retry-After', 1)
                            await asyncio.sleep(int(retry_after) * backoff_factor ** attempt)
                            attempt += 1
                            continue
                        response.raise_for_status()  # This will raise an exception for non-2xx status codes
                        return await response.json()
                except aiohttp.ClientError as e:
                    logging.error(f"Request failed: {e}")
                    return None
            logging.error("Maximum retry attempts reached.")
            return None

    # Helper function to get summoner data
    async def get_summoner_data(self, summoner_name) -> dict:
        return await self.get_api_data(f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}")

    # Helper function to get match history
    async def get_tft_match_history(self, puuid) -> dict:
        return await self.get_api_data(f"https://americas.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count=1")

    # Helper function to get match data
    async def get_tft_match_data(self, match_id) -> dict:
        return await self.get_api_data(f"https://americas.api.riotgames.com/tft/match/v1/matches/{match_id}")

    # Helper function to analyze a match
    async def analyze_tft_game(self, match_id) -> list[str]:
        match_data = await self.get_tft_match_data(match_id)
        if match_data and isinstance(match_data, dict) and 'info' in match_data:
            participants = match_data['info'].get('participants', [])
            analysis = []
            for participant in participants:
                player_name = participant.get('riotIdGameName', 'Unknown Player')
                # Remove both 'TFT13_' and 'tft13_' prefixes
                player_name = player_name.replace("TFT13_", "").replace("tft13_", "")
                placement = participant.get('placement', 'N/A')
                damage = participant.get('total_damage_to_players', 0)

                # Build trait summary
                traits = [f"{trait['name'].replace('TFT13_', '').replace('tft13_', '')} (Tier {trait['tier_current']}/{trait['tier_total']})" 
                            for trait in participant.get('traits', [])]
                trait_summary_text = "\n".join(traits) if traits else "No traits"

                # Build unit summary
                units = [f"{unit['character_id'].replace('TFT13_', '').replace('tft13_', '')} - Tier {unit['tier']}" 
                            for unit in participant.get('units', [])]
                unit_summary_text = "\n".join(units) if units else "No units"

                # Prepare the analysis string
                analysis.append(f"**Player**: {player_name}\n"
                                f"**Placement**: **{placement}**\n"
                                f"**Damage Dealt**: **{damage}**\n\n"
                                f"**Traits**:\n{trait_summary_text}\n\n"
                                f"**Units**:\n{unit_summary_text}\n")
            return analysis
        return ["Could not fetch game data for analysis."]