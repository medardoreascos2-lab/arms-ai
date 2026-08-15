import sqlite3
from pathlib import Path


DATABASE_PATH = Path(
    "backend/storage/trades.db"
)


class JournalDatabase:


    def __init__(self):

        self.connection = sqlite3.connect(
            DATABASE_PATH
        )

        self.create_table()



    def create_table(self):

        cursor = self.connection.cursor()


        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                order_id TEXT,

                symbol TEXT,

                direction TEXT,

                entry REAL,

                stop_loss REAL,

                take_profit REAL,

                contracts INTEGER,

                status TEXT,

                strategy TEXT,

                confidence INTEGER,

                timestamp TEXT

            )
            """
        )


        self.connection.commit()



    def save_trade(
        self,
        trade
    ):

        cursor = self.connection.cursor()


        cursor.execute(
            """
            INSERT INTO trades (

                order_id,
                symbol,
                direction,
                entry,
                stop_loss,
                take_profit,
                contracts,
                status,
                strategy,
                confidence,
                timestamp

            )

            VALUES (?,?,?,?,?,?,?,?,?,?,?)

            """,

            (

                trade.order_id,

                trade.symbol,

                trade.direction,

                trade.entry,

                trade.stop_loss,

                trade.take_profit,

                trade.contracts,

                trade.status,

                trade.strategy,

                trade.confidence,

                trade.timestamp,

            )

        )


        self.connection.commit()



    def get_trades(self):

        cursor = self.connection.cursor()


        cursor.execute(
            "SELECT * FROM trades"
        )


        return cursor.fetchall()
