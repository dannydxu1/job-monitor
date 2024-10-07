import os
import json
import git
from datetime import datetime, timedelta, timezone
import requests
import discord
from dotenv import load_dotenv

load_dotenv()
REPO_URL = 'https://github.com/Ouckah/Summer2025-Internships'
LOCAL_REPO_PATH = 'Summer2025-Internships'
JSON_FILE_PATH = os.path.join(LOCAL_REPO_PATH, '.github', 'scripts', 'listings.json')
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1266849866617720862/Rjfd6mrSbWb1WQyadIOPX4DAZ6xje2wVGuGeCROZPpunIt0bLrC-pp4WU9b-SrUHkgPL"

# Function to clone or update the repository
def clone_or_update_repo():
    if os.path.exists(LOCAL_REPO_PATH):
        try:
            repo = git.Repo(LOCAL_REPO_PATH)
            repo.remotes.origin.pull()
            print("Repository updated.")
        except git.exc.InvalidGitRepositoryError:
            os.rmdir(LOCAL_REPO_PATH)
            git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH)
            print("Repository cloned fresh.")
    else:
        git.Repo.clone_from(REPO_URL, LOCAL_REPO_PATH)
        print("Repository cloned fresh.")

# Function to read JSON file
def read_json():
    with open(JSON_FILE_PATH, 'r') as file:
        data = json.load(file)
    return data

# Function to send a message to Discord using embeds
def send_discord_embed(embed):
    headers = {"Content-Type": "application/json"}
    data = {
        "embeds": [embed.to_dict()]
    }
    response = requests.post(DISCORD_WEBHOOK_URL, json=data, headers=headers)

    if response.status_code == 204:
        print("Message sent successfully.")
    elif response.status_code == 429:  # Rate limited
        retry_after = int(response.headers.get('Retry-After', 0)) / 1000  # Convert ms to seconds
        print(f"Rate limited by Discord. Retrying after {retry_after} seconds.")
        time.sleep(retry_after)
        send_discord_embed(embed)  # Retry after the specified time
    else:
        print(f"Failed to send message. Status code: {response.status_code}, response: {response.text}")

# Function to format the message using an embed
def format_embed_message(role):
    location_str = ', '.join(role['locations']) if role['locations'] else 'Not specified'

    embed = discord.Embed(
        title=f"{role['title']} @ {role['company_name']} ({location_str})",
        url=role['url'],  # This makes the title clickable
        description=f"Season: {role['season']}\nSponsorship: {role['sponsorship']}",
        color=discord.Color.blue(),  # You can change the color if you like
        timestamp=datetime.now(timezone.utc)  # Set timestamp to current time (timezone-aware)
    )

    # Additional fields can be added here
    embed.add_field(name="Job Link", value=f"[Apply here]({role['url']})", inline=False)
    embed.set_footer(text=f"Posted on {datetime.fromtimestamp(role['date_posted'], timezone.utc).strftime('%B %d, %Y')}")

    return embed

# Function to check for new roles based on the timestamp
def check_for_new_roles():
    clone_or_update_repo()

    # Read the current JSON data
    new_data = read_json()

    # Get the current time (timezone-aware) and calculate the time window (e.g., 5 minutes ago)
    current_time = datetime.now(timezone.utc)
    time_window = current_time - timedelta(minutes=30)

    # Find roles posted or updated within the last 5 minutes
    new_roles = [
        role for role in new_data
        if datetime.fromtimestamp(role['date_posted'], timezone.utc) > time_window
    ]

    old_roles = [
        role for role in new_data
        if datetime.fromtimestamp(role['date_posted'], timezone.utc) <= time_window
    ]

    for i in range(min(len(old_roles), 30)):
        temp_role = old_roles[len(old_roles)-i-1]
        print(temp_role['company_name'], datetime.fromtimestamp(temp_role['date_posted'], timezone.utc))

    # if new_roles:
    #     print(f"Found {len(new_roles)} new roles.")
    #     # Send Discord messages for new roles
    #     for role in new_roles:
    #         if role['is_visible'] and role['active']:
    #             embed = format_embed_message(role)
    #             send_discord_embed(embed)
    else:
        print("No new roles found.")

# Main execution
if __name__ == '__main__':
    check_for_new_roles()
