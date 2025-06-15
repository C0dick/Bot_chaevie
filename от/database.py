import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name='tips.db'):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                tip_percent INTEGER NOT NULL,
                total REAL NOT NULL,
                per_person REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                default_tip_percent INTEGER DEFAULT 10
            )
        ''')
        self.conn.commit()

    def save_calculation(self, user_id, amount, tip_percent, total, per_person=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO calculations (user_id, amount, tip_percent, total, per_person)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, amount, tip_percent, total, per_person))
        self.conn.commit()

    def get_history(self, user_id, limit=5):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT amount, tip_percent, total, per_person, timestamp
            FROM calculations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (user_id, limit))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'amount': row[0],
                'tip_percent': row[1],
                'total': row[2],
                'per_person': row[3],
                'timestamp': row[4]
            })
        return history

    def clear_history(self, user_id):
        """НОВЫЙ МЕТОД: Очищает историю расчетов для конкретного пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            DELETE FROM calculations
            WHERE user_id = ?
        ''', (user_id,))
        self.conn.commit()
        return cursor.rowcount  # Возвращает количество удаленных записей

    def set_default_tip(self, user_id, tip_percent):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, default_tip_percent)
            VALUES (?, ?)
        ''', (user_id, tip_percent))
        self.conn.commit()

    def get_default_tip(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT default_tip_percent FROM user_settings WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        return result[0] if result else 10

    def __del__(self):
        self.conn.close()