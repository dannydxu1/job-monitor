import sqlite3

# Connect to SQLite database (or create it if it doesn't exist)
conn = sqlite3.connect('jobs.db')
cursor = conn.cursor()

# Create a table for job listings if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    title TEXT,
    link TEXT,
    date_posted TEXT,
    UNIQUE(title, link, date_posted)
)
''')
conn.commit()

# Close the connection
conn.close()

print("Database setup completed successfully.")
