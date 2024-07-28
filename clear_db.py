import sqlite3

def empty_jobs_table(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM jobs')
        conn.commit()
        print("All rows deleted from the jobs table.")

    except sqlite3.Error as error:
        print(f"Error while connecting to sqlite: {error}")
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    db_path = 'jobs.db'
    empty_jobs_table(db_path)
