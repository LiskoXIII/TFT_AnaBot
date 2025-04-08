import subprocess

def run_postman_collection():
    result = subprocess.run(
        ["newman", "run", "Discord Bot Tests.postman_collection.json"],
        capture_output=True,
        text=True
    )
    print(result.stdout)

run_postman_collection()
