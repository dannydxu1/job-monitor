import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def send_discord_message(webhook_url, message):
    data = {"content": message}
    headers = {"Content-Type": "application/json"}
    response = requests.post(webhook_url, json=data, headers=headers)
    
    if response.status_code != 204:
        raise Exception(f"Failed to send message: {response.status_code}, {response.text}")
    else:
        print("Message sent successfully")

if __name__ == "__main__":
    webhook_url = os.getenv("LOGS_WEBHOOK_URL")  # Get the webhook URL from the environment variable
    if not webhook_url:
        raise Exception("LOGS_WEBHOOK_URL environment variable not set")
    
    role_id = "1252355260161327115"  # Role ID provided by you
    message = f"Hello, <@&{role_id}>! This is a test message from my script!"
    send_discord_message(webhook_url, message)
