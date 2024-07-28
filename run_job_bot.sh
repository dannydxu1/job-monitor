#!/bin/bash

# Change to the directory where your script is located
cd /home/myr/code/job-bot

# Source the virtual environment
source .venv/bin/activate

# Run the Python script and log output
/home/myr/code/job-bot/.venv/bin/python /home/myr/code/job-bot/github_listings.py >> /home/myr/code/job-bot/cronjob.log 2>&1
