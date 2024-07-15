import os
import sqlite3


class Database:
    def __init__(self, base_dir, db_path):
        full_db_path = os.path.abspath(os.path.join(base_dir, db_path))
        # db_path = os.path.join(os.path.dirname(__file__), db_path)
        if not os.path.exists(full_db_path):
            with open(full_db_path, "w", encoding="utf-8"):
                pass
        self.conn = sqlite3.connect(full_db_path)
        self.c = self.conn.cursor()

    def create_table(self):
        self.c.execute(
            """CREATE TABLE IF NOT EXISTS pinned_messages
                    (id INTEGER PRIMARY KEY, message TEXT,
                       date DATETIME, photo BLOB)"""
        )
        self.conn.commit()

    def table_exists(self, table_name):
        self.c.execute(
            """SELECT name FROM sqlite_master
                       WHERE type='table' AND name=?""",
            (table_name,),
        )
        return self.c.fetchone() is not None

    def insert_or_ignore(self, values, print_diff):
        if print_diff:
            print(f"Before: {self.get_count()}")

        self.c.executemany(
            """INSERT OR IGNORE INTO pinned_messages
                           (id, message, date, photo)
                           VALUES (?, ?, ?, ?)""",
            values,
        )

        if print_diff:
            print(f"After: {self.get_count()}")
        self.conn.commit()

    def delete_dups(self, messages):
        self.c.execute(
            f"""DELETE FROM pinned_messages WHERE id NOT IN
                       ({', '.join('?' for _ in messages)})""",
            messages,
        )
        self.conn.commit()

    def get_count(self):
        self.c.execute("""SELECT COUNT(*) FROM pinned_messages""")
        return self.c.fetchone()[0]

    def get_message_by_id(self, message_id):
        self.c.execute(
            """SELECT * FROM pinned_messages
                       WHERE id = ?""",
            (message_id,),
        )
        return self.c.fetchone()

    def get_random_messages(self, count):
        self.c.execute(
            f"""SELECT * FROM pinned_messages
                       ORDER BY RANDOM() LIMIT {count}"""
        )
        return self.c.fetchall()

    def get_recent_messages(self, date_value):
        self.c.execute(
            """SELECT * FROM pinned_messages
                       WHERE date >= ?""",
            (date_value,),
        )
        return self.c.fetchall()

    def close(self):
        self.conn.close()
