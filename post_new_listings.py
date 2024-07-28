import requests
import re
import csv
from datetime import datetime
from dotenv import load_dotenv
import os
from github import Github

load_dotenv()  # Load environment variables from .env file

# URL of the GitHub repository's README in raw format
REPO_URL = os.getenv("JOB_REPO_URL")
LISTINGS_WEBHOOK_URL = os.getenv("LISTINGS_WEBHOOK_URL")
LOGS_WEBHOOK_URL = os.getenv("LOGS_WEBHOOK_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")  # Format: "username/repo"
CSV_FILE_PATH = "./listings.csv"

# GitHub instance
github = Github(GITHUB_TOKEN)
repo = github.get_repo(REPO_NAME)


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


def read_csv():
    listings = []
    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        decoded_content = contents.decoded_content.decode()
        reader = csv.reader(decoded_content.splitlines())
        next(reader)  # Skip header
        for row in reader:
            listings.append(tuple(row))
    except Exception as e:
        print(f"Error reading CSV file: {e}")
    return listings


def write_csv(listings):
    header = ["company", "job_title", "link", "date_posted"]
    csv_content = ",".join(header) + "\n"
    for listing in listings:
        print(".")
        csv_content += ",".join(listing[:4]) + "\n"
    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        repo.update_file(
            contents.path, "Update job listings", csv_content, contents.sha
        )
    except Exception as e:
        repo.create_file(CSV_FILE_PATH, "Create job listings file", csv_content)


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
    existing_listings = read_csv()

    for company, job_title, link, date_posted, formatted_listing in listings:
        # Check if the listing already exists in the CSV file
        if (company, job_title, link, date_posted) not in existing_listings:
            new_listings_found = True
            # Add the listing to the message
            message += f"{formatted_listing}\n"
            # Add the listing to the CSV content
            existing_listings.append((company, job_title, link, date_posted))

    if new_listings_found:
        write_csv(existing_listings)
    # parts = split_message(message)
    # for part in parts:
    #     send_discord_alert(part)


if __name__ == "__main__":
    main()
