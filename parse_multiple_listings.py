import requests
import re
import csv
from datetime import datetime
from dotenv import load_dotenv
import os
import json
from github import Github
import sys

load_dotenv()  #
PRIMARY_REPO = os.getenv("JOB_REPO_URL")
SECONDARY_REPO = os.getenv("SECONDARY_REPO_URL")
LISTINGS_WEBHOOK_URL = os.getenv("LISTINGS_WEBHOOK_URL")
LOGS_WEBHOOK_URL = os.getenv("LOGS_WEBHOOK_URL")
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
REPO_NAME = os.getenv("REPO_NAME")  # Format: "username/repo"
CSV_FILE_PATH = "./listings.csv"

github = Github(GITHUB_TOKEN)
repo = github.get_repo(REPO_NAME)

log_file = open("logs.txt", "w")
sys.stdout = log_file
result_message = "" 


def process_match_groups(company, job_title, link_html, last_company):
    company_pattern = re.compile(r"\*\*\[([^\]]+)\]")
    company_pattern_match = company_pattern.search(company)
    if company_pattern_match:
        company = company_pattern_match.group(1)
    if "↳" in company:  # this has to be after the first company assignment
        company = last_company
    company = company.replace(",", "")
    job_title = job_title.replace(",", "").replace("🛂", "")
    link_match = re.search(r'href="([^"]+)"', link_html)
    link = f"<{link_match.group(1)}>" if link_match else "No link found"

    return company, job_title, link


def parse_readme(content):
    listings = (
        {}
    )  # {Company: {Job Title: {link, date_posted, formatted_listing}, ...}, ...}
    listing_pattern = re.compile(
        r'\| ([^|]+) \| ([^|]+) \| [^|]+ \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )
    arrow_listing_pattern = re.compile(
        r'\| ↳ \| ([^|]+) \| ([^|]+) \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )

    lines = content.split("\n")
    last_company = ""
    for line in lines:
        normal_match = listing_pattern.match(line)
        arrow_match = arrow_listing_pattern.match(line)
        match = normal_match if normal_match else arrow_match

        if match:
            company, job_title, link_html, date_posted = match.groups()
            company, job_title, link = process_match_groups(
                company, job_title, link_html, last_company
            )
            formatted_listing = f"**{company}** - {job_title}\nApply: {link}\nDate Posted: {date_posted}"

            if company not in listings:
                listings[company] = {}

            listings[company][job_title] = {
                "link": link,
                "date_posted": date_posted,
                "formatted_listing": formatted_listing,
            }
            if "↳" not in company:
                last_company = company

    return listings


def fetch_github_listings(url):
    response = requests.get(url)
    response.raise_for_status()
    readme = response.text
    listings = parse_readme(readme)
    return listings


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
    c = 0
    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        decoded_content = contents.decoded_content.decode()
        reader = csv.reader(decoded_content.splitlines())
        next(reader)  # Skip header
        for row in reader:
            listings.add(tuple(row))
            c += 1
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
    print(f"CSV began with {c} unique rows")
    return listings


def append_to_csv(new_listings):
    """
    Append new job listings to the CSV file in the GitHub repository.

    This function takes a list of new job listings and appends them to an existing CSV file in the specified GitHub repository.
    If the CSV file does not exist, it creates a new CSV file with the given listings.

    Args:
        new_listings (list): A list of tuples, where each tuple represents a job listing.
                             Each tuple should contain the following four elements:
                             (company, job_title, link, date_posted).

    Returns:
        None

    Behavior:
        - If `new_listings` is empty, the function returns immediately without doing anything.
        - If the CSV file exists, the function reads the current contents, appends the new listings, and updates the file in the repository.
        - If the CSV file does not exist, the function creates a new CSV file with the provided listings.

    Example:
        new_listings = [
            ("Company A", "Software Engineer", "<http://example.com/apply>", "Jul 29"),
            ("Company B", "Data Scientist", "<http://example.com/apply>", "Jul 30")
        ]
        append_to_csv(new_listings)
    """
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


def print_dict(dict_obj):
    formatted_dict = json.dumps(dict_obj, indent=4)
    print(formatted_dict)


def print_listings(listings):
    for listing in listings:
        print(listing)


def process_listings(url):
    response = requests.get(url)
    response.raise_for_status()
    content = response.text
    listings = (
        {}
    )  # {Company: {Job Title: {link, date_posted, formatted_listing}, ...}, ...}
    listing_pattern = re.compile(
        r'\| ([^|]+) \| ([^|]+) \| [^|]+ \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )
    arrow_listing_pattern = re.compile(
        r'\| ↳ \| ([^|]+) \| ([^|]+) \| (<a href="[^"]+"><img src="[^"]+" width="\d+" alt="Apply"></a>.*?) \| (\w+ \d{2}) \|'
    )

    lines = content.split("\n")
    last_company = ""
    for line in lines:
        normal_match = listing_pattern.match(line)
        arrow_match = arrow_listing_pattern.match(line)
        match = normal_match if normal_match else arrow_match

        if match:
            company, job_title, link_html, date_posted = match.groups()
            company, job_title, link = process_match_groups(
                company, job_title, link_html, last_company
            )
            formatted_listing = f"**{company}** - {job_title}\nApply: {link}\nDate Posted: {date_posted}"

            if company not in listings:
                listings[company] = {}

            listings[company][job_title] = {
                "link": link,
                "date_posted": date_posted,
                "formatted_listing": formatted_listing,
            }
            if "↳" not in company:
                last_company = company

    return listings


def remove_utm_source(url):
    substrings_to_remove = [
        "&utm_source=Simplify&ref=Simplify",
        "?utm_source=Simplify&ref=Simplify",
        "&utm_source=Simplify",
        "&utm_source=GH_List",
    ]

    # Remove each substring from the url
    for substring in substrings_to_remove:
        # if substring in url:
        #     print("removed")
        url = url.replace(substring, "")

    return url


def remove_duplicates(current, primary, secondary):
    new_listings = []  # stores the formatted listings
    dupe = 0
    # Process Secondary Listings
    pt = 0
    pa = 0
    sa = 0
    st = 0
    for company, jobs in secondary.items():
        for job_title, details in jobs.items():
            current_listing = (
                company,
                job_title,
                details["link"][1:-1],
                details["date_posted"],
            )
            st += 1
            if current_listing not in current:
                new_listings.append(details["formatted_listing"])
                current.add(current_listing)
                sa += 1

    # Process Primary Listings
    for company, jobs in primary.items():
        for (
            job_title,
            details,
        ) in (
            jobs.items()
        ):  # Process the current primary listing, check if it is a duplicate
            pt += 1
            seconday_company_dict = secondary.get(company)
            in_secondary = False
            if (
                seconday_company_dict
            ):  # Current listing's company is also a company in the secondary listings
                for (
                    seconday_job_title,
                    secondary_details,
                ) in seconday_company_dict.items():
                    if (
                        job_title == seconday_job_title
                    ):  # Duplicate job listing detected
                        dupe += 1
                        in_secondary = True
                        break
                    seconday_link, primary_link = remove_utm_source(
                        secondary_details["link"]
                    ), remove_utm_source(details["link"])
                    if (
                        seconday_link in primary_link or primary_link in seconday_link
                    ):  # Duplicate job listing detected
                        dupe += 1
                        in_secondary = True
                        break

            if in_secondary:
                continue  # Skip the current primary listing b/c it is a duplicate

            current_listing = (
                company,
                job_title,
                details["link"][1:-1],
                details["date_posted"],
            )
            if current_listing not in current:
                current.add(current_listing)
                pa += 1
                new_listings.append(details["formatted_listing"])
    result_message = f"Total Primary Listings: {pt} | Total Secondary Listings: {st} | Total Listings: {pt+st}\nNew Primary Listings: {pa} | New Secondary Listings: {sa} | Total New Listings: {pa+sa}"
    print(result_message)
    return new_listings


def extract_listing_details(listing_str):
    # Define regex pattern to extract company, job_title, link, and date_posted
    pattern = re.compile(r"\*\*(.*?)\*\* - (.*?)\nApply: <(.*?)>\nDate Posted: (.*?)$")
    match = pattern.match(listing_str)

    if match:
        company, job_title, link, date_posted = match.groups()
        return company, job_title, link, date_posted
    return None


def print_listing_tuples(listings):
    for listing in listings:
        details = extract_listing_details(listing)
        if details:
            company, job_title, link, date_posted = details
            print(f"({company},{job_title},{link},{date_posted})")


def create_and_send_discord_message(new_listings):
    today = datetime.now().strftime("%Y-%m-%d")
    header = f"**Job Listings for {today} <@&{1252355260161327115}>!**\n"
    message = header

    for listing in new_listings:
        message += f"{listing}\n"

    parts = split_message(message)
    for part in parts:
        send_discord_alert(part)
    new_listings_message = f"Found {len(new_listings)} new listings"
    send_discord_alert(new_listings_message, LOGS_WEBHOOK_URL)


def main():
    current_listings = read_csv()
    secondary_listings = process_listings(SECONDARY_REPO)
    primary_listings = process_listings(PRIMARY_REPO)

    new_listings = remove_duplicates(
        current_listings, primary_listings, secondary_listings
    )

    if len(new_listings) > 0:
        create_and_send_discord_message(new_listings)
        new_listing_tuples = []  # Convert each new listing to tuple and save it to CSV
        for listing in new_listings:
            listing_tuple = extract_listing_details(listing)
            if listing_tuple:
                new_listing_tuples.append(listing_tuple)
        append_to_csv(new_listing_tuples)
        send_discord_alert(result_message, LOGS_WEBHOOK_URL)


if __name__ == "__main__":
    main()
    log_file.close
