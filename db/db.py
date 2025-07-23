"""
Module to handle database operations.
"""

import logging
import os
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """
    A class to represent a database object using SQLite3.
    """

    def __init__(self, base_dir: str, db_path: str):
        """
        Initializes the Database object.

        Args:
            base_dir (str): The base directory of the project.
            db_path (str): The path to the database file.
        """
        full_db_path = os.path.abspath(os.path.join(base_dir, db_path))
        if not os.path.exists(full_db_path):
            with open(full_db_path, "w", encoding="utf-8"):
                pass
        self.conn = sqlite3.connect(full_db_path)
        self.c = self.conn.cursor()

    def create_table(self, table_name) -> None:
        """
        Creates the specified table if it doesn't exist.

        Args:
            table_name (str): The name of the table to create.
        """
        self.c.execute(
            f"""CREATE TABLE IF NOT EXISTS {table_name}
                    (id INTEGER PRIMARY KEY, message_id INTEGER UNIQUE,
                    message TEXT, date DATETIME, photo BLOB)""",
        )
        self.conn.commit()

    def table_exists(self, table_name: str) -> bool:
        """
        Checks if the specified table exists in the database.

        Args:
            table_name (str): The name of the table to check.

        Returns:
            bool: True if the table exists, False otherwise.
        """
        self.c.execute(
            """SELECT name FROM sqlite_master
                       WHERE type='table' AND name=?""",
            (table_name,),
        )
        return self.c.fetchone() is not None

    def insert_or_ignore(
        self,
        table_name: str,
        values: list[tuple[int, str, datetime, bytes | None]],
        get_last_update: bool,
    ) -> None | str:
        """
        Inserts the given values into the pinned_messages table, ignoring
        any duplicates.

        Args:
            table_name (str): The name of the table to insert into.
            values (list[tuple[int, str, datetime, bytes | None]]): The values
                to insert into the table.
            get_last_update (bool): Whether to return the last update date.

        Returns:
            None | str: The last update date if get_last_update is True.
        """
        last_update = self.get_last_update(table_name)
        logger.debug(f"Last update: {last_update}")

        self.c.executemany(
            f"""INSERT OR IGNORE INTO {table_name}
                        (message_id, message, date, photo)
                        VALUES (?, ?, ?, ?)""",
            (values),
        )

        self.conn.commit()

        if get_last_update:
            return last_update

    def remove_messages(self, table_name: str, message_ids: list[int]) -> None:
        """
        Removes messages from the specified table that are not in the
        given list of message IDs.

        Args:
            table_name (str): The name of the table to remove messages from.
            message_ids (list[int]): The list of message IDs to keep.
        """
        placeholders = ", ".join("?" * len(message_ids))
        query = f"""DELETE FROM {table_name}
                    WHERE message_id NOT IN ({placeholders})"""

        self.c.execute(
            query,
            (message_ids),
        )
        self.conn.commit()

    def get_count(self, table_name: str) -> int:
        """
        Gets the number of rows in the specified table.

        Args:
            table_name (str): The name of the table to count rows in.

        Returns:
            int: The number of rows in the table.
        """
        self.c.execute(
            f"""SELECT COUNT(*) FROM {table_name}""",
        )
        return self.c.fetchone()[0]

    def get_last_update(self, table_name: str) -> str:
        """
        Gets the most recent date in the specified table.

        Args:
            table_name (str): The name of the table to get the last update from.

        Returns:
            str: The most recent date in the table.
        """
        self.c.execute(f"""SELECT MAX(date) FROM {table_name}""")
        return self.c.fetchone()[0]

    def get_message_by_id(self, table_name: str, message_id: int) -> tuple:
        """
        Gets a message from the specified table by its message ID.

        Args:
            table_name (str): The name of the table to search in.
            message_id (int): The message ID to search for.

        Returns:
            tuple: The message with the given message ID
        """
        self.c.execute(
            f"""SELECT * FROM {table_name}
                       WHERE message_id = ?""",
            (message_id,),
        )
        return self.c.fetchone()

    def get_random_messages(self, count: int) -> list:
        """
        Gets a random selection of messages from the pinned_messages table,
        up to the specified count.

        Args:
            count (int): The number of messages to get.

        Returns:
            list: A list of randomly selected messages.
        """
        self.c.execute(
            f"""SELECT * FROM pinned_messages
                       ORDER BY RANDOM() LIMIT {count}"""
        )
        return self.c.fetchall()

    def get_recent_messages_by_date(
        self, table_name: str, date_value: str | datetime
    ) -> list:
        """
        Gets messages from the specified table that are more recent than
        the given date.

        Args:
            table_name (str): The name of the table to search in.
            date_value (str | datetime): The date to compare against.

        Returns:
            list: A list of messages more recent than the given date.
        """
        self.c.execute(
            f"""SELECT * FROM {table_name}
                       WHERE date > ?""",
            (date_value,),
        )
        return self.c.fetchall()

    def get_recent_messages_by_row_id(self, table_name: str, row_id: int) -> list:
        """
        Gets messages from the specified table that have a row ID greater
        than or equal to the given value.
        Note: oldest messages have the lowest row ID.

        Args:
            table_name (str): The name of the table to search in.
            row_id (int): The row ID to compare against.

        Returns:
            list: A list of messages with row IDs greater than or equal to the
                given value.
        """
        self.c.execute(
            f"""SELECT * FROM {table_name}
                       WHERE id >= ?""",
            (row_id,),
        )
        return self.c.fetchall()

    def close(self):
        """
        Closes the database connection.
        """
        self.conn.close()
