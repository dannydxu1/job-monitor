import os
from github import Github
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# Load environment variables
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_NAME = os.getenv("REPO_NAME")  # Format: "username/repo"
CSV_FILE_PATH = "./listings.csv"  # Path to the CSV file in the repo

# GitHub instance
github = Github(GITHUB_TOKEN)
repo = github.get_repo(REPO_NAME)

def delete_csv_file():
    try:
        contents = repo.get_contents(CSV_FILE_PATH)
        repo.delete_file(contents.path, "Delete job listings file", contents.sha)
        print(f"Deleted {CSV_FILE_PATH} successfully.")
    except Exception as e:
        print(f"Error deleting CSV file: {e}")

if __name__ == "__main__":
    delete_csv_file()
