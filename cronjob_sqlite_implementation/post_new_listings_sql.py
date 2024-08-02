import requests
import re
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()  # Load environment variables from .env file

# URL of the GitHub repository's README in raw format
REPO_URL = os.getenv("JOB_REPO_URL")
LISTINGS_WEBHOOK_URL = os.getenv("LISTINGS_WEBHOOK_URL")
LOGS_WEBHOOK_URL = os.getenv("LOGS_WEBHOOK_URL")

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect("jobs.db")
cursor = conn.cursor()

# Create a table for job listings if it doesn't exist
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    company TEXT,
    job_title TEXT,
    link TEXT,
    date_posted TEXT,
    UNIQUE(company, job_title, link, date_posted)
)
"""
)
conn.commit()


def fetch_readme(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.text


def parse_readme(content):
    listings = []

    pattern_unlinked = re.compile(
        r'\| ([^|]+) \| ([^|]+) \| [^|]+ \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )
    pattern_arrow = re.compile(
        r'\| ↳ \| ([^|]+) \| ([^|]+) \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )

    # Split the content into lines and process each line
    lines = content.split("\n")
    last_company = ""
    for line in lines:
        unlinked_match, arrow_match = (
            pattern_unlinked.match(line),
            pattern_arrow.match(line),
        )
        match = unlinked_match

        if match:
            company, job_title, link_html, date_posted = match.groups()
            company_pattern = re.compile(r"\*\*\[([^\]]+)\]")
            company_pattern_match = company_pattern.search(company)
            if company_pattern_match:
                company = company_pattern_match.group(1)
            if "↳" in company:  # this has to be after the first company assignment
                company = last_company
            link_match = re.search(r'href="([^"]+)"', link_html)
            link = f"<{link_match.group(1)}>" if link_match else "No link found"
            formatted_listing = f"**{company}** - {job_title}\nApply: {link}\nDate Posted: {date_posted}"
            listings.append((company, job_title, link, date_posted, formatted_listing))
            if "↳" not in company:
                last_company = company
    return listings


def fetch_github_listings(repo_url=REPO_URL):
    readme_content = fetch_readme(repo_url)
    return parse_readme(readme_content)


def send_discord_alert(message, target_url=LISTINGS_WEBHOOK_URL):
    data = {"content": message}
    headers = {"Content-Type": "application/json"}
    response = requests.post(target_url, json=data, headers=headers)
    if response.status_code != 204:
        raise Exception(
            f"Failed to send message: {response.status_code}, {response.text}"
        )


def split_message(message, limit=2000):
    lines = message.split("\n")
    parts = []
    current_part = ""
    for line in lines:
        if len(current_part) + len(line) + 1 > limit:
            parts.append(current_part)
            current_part = line
        else:
            if current_part:
                current_part += "\n"
            current_part += line
    if current_part:
        parts.append(current_part)
    return parts


def main():
    bot_health_message = "bot is running at " + datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    send_discord_alert(bot_health_message, LOGS_WEBHOOK_URL)
    listings = fetch_github_listings()
    today = datetime.now().strftime("%Y-%m-%d")
    header = f"**Job Listings for {today}**\n\n"

    message = header
    new_listings_found = False

    for company, job_title, link, date_posted, formatted_listing in listings:
        # Check if the listing already exists in the database
        cursor.execute(
            "SELECT * FROM jobs WHERE company=? AND job_title=? AND link=? AND date_posted=?",
            (company, job_title, link, date_posted),
        )
        result = cursor.fetchone()

        if result is None:
            new_listings_found = True
            # Add the listing to the message
            message += f"{formatted_listing}\n"
            # Insert the listing into the database
            cursor.execute(
                "INSERT INTO jobs (company, job_title, link, date_posted) VALUES (?, ?, ?, ?)",
                (company, job_title, link, date_posted),
            )
            conn.commit()

    if new_listings_found:
        parts = split_message(message)
        for part in parts:
            send_discord_alert(part)


if __name__ == "__main__":
    main()
    conn.close()
