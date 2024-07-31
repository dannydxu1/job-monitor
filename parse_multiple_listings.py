import requests
import re
import csv
from datetime import datetime
from dotenv import load_dotenv
import os
from github import Github
import sys

load_dotenv()  #
JOB_REPO_URL = os.getenv("JOB_REPO_URL")
SECONDARY_REPO_URL = os.getenv("SECONDARY_REPO_URL")
LISTINGS_WEBHOOK_URL = os.getenv("LISTINGS_WEBHOOK_URL")
LOGS_WEBHOOK_URL = os.getenv("LOGS_WEBHOOK_URL")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
REPO_NAME = os.getenv("REPO_NAME")  # Format: "username/repo"
CSV_FILE_PATH = "./listings.csv"

github = Github(GITHUB_TOKEN)
repo = github.get_repo(REPO_NAME)


def parse_readme(content):
    listings, unique_listings = [], set()
    listing_pattern = re.compile(
        r'\| ([^|]+) \| ([^|]+) \| [^|]+ \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )
    arrow_listing_pattern = re.compile(
        r'\| ↳ \| ([^|]+) \| ([^|]+) \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )

    lines = content.split("\n")
    last_company = ""
    for line in lines:
        unlinked_match, arrow_match = (
            listing_pattern.match(line),
            arrow_listing_pattern.match(line),
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
            job_title = job_title.replace(",", "")
            job_title = job_title.replace("🛂", "")
            link_match = re.search(r'href="([^"]+)"', link_html)
            link = f"<{link_match.group(1)}>" if link_match else "No link found"
            formatted_listing = f"**{company}** - {job_title}\nApply: {link}\nDate Posted: {date_posted}"
            listings.append((company, job_title, link, date_posted, formatted_listing))
            unique_listings.add(
                (company, job_title, link, date_posted, formatted_listing)
            )
            if "↳" not in company:
                last_company = company
    return listings, unique_listings


def fetch_github_listings(url):
    response = requests.get(url)
    response.raise_for_status()
    readme = response.text
    listings, unique_listings = parse_readme(readme)
    return listings, unique_listings


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


def create_csv():
    header = ["company", "job_title", "link", "date_posted"]
    csv_content = ",".join(header) + "\n"
    try:
        repo.create_file(CSV_FILE_PATH, "Create job listings file", csv_content)
        print(f"Created {CSV_FILE_PATH} successfully.")
    except Exception as e:
        print(f"Error creating CSV file: {e}")


def read_csv():
    listings = set()
    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        decoded_content = contents.decoded_content.decode()
        reader = csv.reader(decoded_content.splitlines())
        next(reader)  # Skip header
        for row in reader:
            listings.add(tuple(row))
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        create_csv()  # Create the file if it does not exist
        try:
            contents = repo.get_contents(CSV_FILE_PATH)
            decoded_content = contents.decoded_content.decode()
            reader = csv.reader(decoded_content.splitlines())
            next(reader)  # Skip header
            for row in reader:
                listings.add(tuple(row))
        except Exception as e:
            print(f"Error reading newly created CSV file: {e}")
    return listings


def append_to_csv(new_listings):
    if not new_listings:
        return

    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        csv_content = contents.decoded_content.decode()
        new_csv_content = csv_content.strip() + "\n"
        for listing in new_listings:
            new_csv_content += ",".join(listing[:4]) + "\n"
        repo.update_file(
            contents.path, "Append new job listings", new_csv_content, contents.sha
        )

    except Exception:
        # Create the file if it doesn't exist
        header = ["company", "job_title", "link", "date_posted"]
        csv_content = ",".join(header) + "\n"
        for listing in new_listings:
            csv_content += ",".join(listing[:4]) + "\n"
        repo.create_file(CSV_FILE_PATH, "Create job listings file", csv_content)


def main():
    job_listings = fetch_github_listings(JOB_REPO_URL)
    secondary_listings = fetch_github_listings(SECONDARY_REPO_URL)
    print(job_listings)
    # today = datetime.now().strftime("%Y-%m-%d")
    # header = f"**Job Listings for {today}**\n\n"
    # message = header

    # new_listings = []
    # existing_listings = read_csv()
    # print(len(existing_listings))
    # # Convert secondary_listings to a set of links for faster lookups
    # secondary_links_set = {listing[2][1:-1] for listing in secondary_listings}

    # # Add secondary listings if they don't exist already in csv
    # new_secondary_jobs = 0
    # new_primary_jobs = 0
    # for company, job_title, link, date_posted, formatted_listing in secondary_listings:
    #     if (company, job_title, link, date_posted) not in existing_listings:
    #         message += f"{formatted_listing}\n"
    #         new_listings.append((company, job_title, link, date_posted))
    #         new_secondary_jobs += 1
    # temp = []
    # # Go through each primary listing and add them if they don't exist in secondary listing
    # utm_pattern = re.compile(r"(.*?utm_source=[a-zA-Z]+)")
    # for job_listing in job_listings:
    #     job_link = job_listing[2][1:-1]  # Remove the angle brackets
    #     utm_match = utm_pattern.match(job_link)
    #     if utm_match:
    #         job_link_base = utm_match.group(1)
    #         for secondary_listing in secondary_listings:
    #             secondary_link = secondary_listing[2][1:-1]  # Remove the angle brackets
    #             if job_link_base in secondary_link or secondary_link in job_link_base:
    #                 # print(f"Job Link: {job_link}")
    #                 # print(f"Secondary Link: {secondary_link}")
    #                 break
    #     else:
    #         if (
    #             job_listing[2] not in secondary_links_set
    #             and (job_listing[0], job_listing[1], job_listing[2], job_listing[3])
    #             not in existing_listings
    #         ):
    #             message += f"{job_listing[4]}\n"
    #             temp.append(
    #                 (job_listing[0], job_listing[1], job_listing[2], job_listing[3])
    #             )
    #             new_listings.append(
    #                 (job_listing[0], job_listing[1], job_listing[2], job_listing[3])
    #             )
    #             new_primary_jobs += 1
    # print(new_primary_jobs, new_secondary_jobs)
    # print(len(new_listings))

    # result_message = f"Found {len(new_listings)} new listings and {len(existing_listings)} existing listings."
    # if len(new_listings) > 0:
    #     append_to_csv(new_listings)
    #     parts = split_message(message)
    #     for part in parts:
    #         send_discord_alert(part)
    # send_discord_alert(result_message, LOGS_WEBHOOK_URL)


if __name__ == "__main__":
    main()
