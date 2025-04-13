import subprocess
import json
import os

import envs

def run_postman_collection():

    envs.set_envs()

    with open("Discord Bot Tests.postman_collection.json", "r") as f:
        data = json.load(f)
        data["item"][0]["request"]["header"][0]["value"] = os.getenv("RIOT_API_KEY")
        data["item"][1]["request"]["header"][0]["value"] = os.getenv("RIOT_API_KEY")
        data["item"][2]["request"]["header"][0]["value"] = os.getenv("RIOT_API_KEY")

    with open("Discord Bot Tests.postman_collection.json", "w") as f:
        json.dump(data, f, indent=4)

    result = subprocess.run(
        ["newman", "run", "Discord Bot Tests.postman_collection.json"],
        capture_output=True,
        text=True
    )
    print(result.stdout)

run_postman_collection()
