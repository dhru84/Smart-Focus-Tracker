import sqlite3
import json
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class UserContext:
    """User context for personalized interventions"""
    typical_productive_hours: List[int]
    distraction_patterns: Dict[str, float]
    response_history: List[Dict]
    productivity_score: float
    stress_indicators: List[str]


class DatabaseManager:
    """Database manager for productivity data using SQLite"""

    def __init__(self, db_name='productivity.db'):
        self.db_name = db_name
        self.lock = threading.Lock()
        
    def _get_connection(self):
        """Get a new database connection with foreign keys enabled"""
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        # Add this line to enforce foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def initialize_database(self):
        """Initialize all necessary database tables"""
        with self.lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            try:
                # Users table (optional, for future expansion)
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        created_at TEXT
                    )
                ''')

                # Distraction URLs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS distraction_urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        url TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Productive URLs
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS productive_urls (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        url TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Usage data
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS usage_data (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        url TEXT,
                        domain TEXT,
                        duration INTEGER,
                        interactions_json TEXT,
                        timestamp TEXT,
                        is_distraction BOOLEAN,
                        is_productive BOOLEAN,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Tab activity
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tab_activity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        url TEXT,
                        title TEXT,
                        timestamp TEXT,
                        time_of_day INTEGER,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Intervention responses
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS intervention_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT,
                        domain TEXT,
                        answer TEXT,
                        timestamp TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Distraction limits
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS distraction_limits (
                        user_id TEXT,
                        domain TEXT,
                        limit_minutes INTEGER,
                        PRIMARY KEY (user_id, domain),
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                # Productive targets
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS productive_targets (
                        user_id TEXT,
                        domain TEXT,
                        target_minutes INTEGER,
                        PRIMARY KEY (user_id, domain),
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )
                ''')

                conn.commit()
                print("Database tables initialized successfully")
                
            except Exception as e:
                print(f"Error initializing database: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def _ensure_user_exists(self, user_id: str, conn=None):
        """Helper to ensure user exists in users table"""
        should_close = False
        if conn is None:
            conn = self._get_connection()
            should_close = True
            
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO users (user_id, created_at) VALUES (?, ?)',
                              (user_id, datetime.now().isoformat()))
                conn.commit()
        except Exception as e:
            print(f"Error ensuring user exists: {e}")
            conn.rollback()
            raise
        finally:
            if should_close:
                conn.close()

    def store_distraction_urls(self, user_id: str, urls: List[str]):
        """Store distraction URLs for a user"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(user_id, conn)
                cursor = conn.cursor()
                
                # Delete existing for user to update
                cursor.execute('DELETE FROM distraction_urls WHERE user_id = ?', (user_id,))
                
                # Insert new URLs
                for url in urls:
                    if url and isinstance(url, str):  # Validate URL
                        cursor.execute('INSERT INTO distraction_urls (user_id, url) VALUES (?, ?)', (user_id, url))
                
                conn.commit()
                print(f"Stored {len(urls)} distraction URLs for user {user_id}")
                
            except Exception as e:
                print(f"Error storing distraction URLs: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def store_productive_urls(self, user_id: str, urls: List[str]):
        """Store productive URLs for a user"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(user_id, conn)
                cursor = conn.cursor()
                
                # Delete existing for user to update
                cursor.execute('DELETE FROM productive_urls WHERE user_id = ?', (user_id,))
                
                # Insert new URLs
                for url in urls:
                    if url and isinstance(url, str):  # Validate URL
                        cursor.execute('INSERT INTO productive_urls (user_id, url) VALUES (?, ?)', (user_id, url))
                
                conn.commit()
                print(f"Stored {len(urls)} productive URLs for user {user_id}")
                
            except Exception as e:
                print(f"Error storing productive URLs: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def store_usage_data(self, usage_entry: Dict):
        """Store usage data entry"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(usage_entry['user_id'], conn)
                cursor = conn.cursor()
                
                # Serialize interactions to JSON
                interactions_json = json.dumps(usage_entry.get('interactions', {}))
                
                # Ensure timestamp is a string
                timestamp = usage_entry.get('timestamp')
                if not isinstance(timestamp, str):
                    timestamp = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT INTO usage_data 
                    (user_id, url, domain, duration, interactions_json, timestamp, is_distraction, is_productive)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    usage_entry['user_id'], 
                    usage_entry.get('url', ''), 
                    usage_entry.get('domain', ''), 
                    int(usage_entry.get('duration', 0)),
                    interactions_json, 
                    timestamp, 
                    bool(usage_entry.get('is_distraction', False)), 
                    bool(usage_entry.get('is_productive', False))
                ))
                
                conn.commit()
                print(f"Stored usage data for user {usage_entry['user_id']}")
                
            except Exception as e:
                print(f"Error storing usage data: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def store_tab_activity(self, tab_data: Dict):
        """Store tab activity data"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(tab_data['user_id'], conn)
                cursor = conn.cursor()
                
                # Ensure timestamp is a string
                timestamp = tab_data.get('timestamp')
                if not isinstance(timestamp, str):
                    timestamp = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT INTO tab_activity 
                    (user_id, url, title, timestamp, time_of_day)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    tab_data['user_id'], 
                    tab_data.get('url', ''), 
                    tab_data.get('title', ''), 
                    timestamp, 
                    int(tab_data.get('time_of_day', datetime.now().hour))
                ))
                
                conn.commit()
                print(f"Stored tab activity for user {tab_data['user_id']}")
                
            except Exception as e:
                print(f"Error storing tab activity: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def store_intervention_response(self, interaction: Dict):
        """Store intervention response"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(interaction['user_id'], conn)
                cursor = conn.cursor()
                
                # Ensure timestamp is a string
                timestamp = interaction.get('timestamp')
                if not isinstance(timestamp, str):
                    timestamp = datetime.now().isoformat()
                
                cursor.execute('''
                    INSERT INTO intervention_responses 
                    (user_id, domain, answer, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (
                    interaction['user_id'], 
                    interaction.get('domain', ''), 
                    interaction.get('answer', ''), 
                    timestamp
                ))
                
                conn.commit()
                print(f"Stored intervention response for user {interaction['user_id']}")
                
            except Exception as e:
                print(f"Error storing intervention response: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_user_context(self, user_id: str) -> UserContext:
        """Get or compute user context (simplified computation for demo)"""
        conn = self._get_connection()
        try:
            self._ensure_user_exists(user_id, conn)
            cursor = conn.cursor()
            
            # Compute typical productive hours (e.g., hours with more productive usage)
            cursor.execute('''
                SELECT strftime('%H', timestamp) as hour, SUM(duration) as total
                FROM usage_data 
                WHERE user_id = ? AND is_productive = 1
                GROUP BY hour
                ORDER BY total DESC
                LIMIT 5
            ''', (user_id,))
            result = cursor.fetchall()
            productive_hours = [int(row[0]) for row in result if row[0] is not None]
            
            # Distraction patterns (domain -> avg duration)
            cursor.execute('''
                SELECT domain, AVG(duration) as avg_duration
                FROM usage_data 
                WHERE user_id = ? AND is_distraction = 1
                GROUP BY domain
            ''', (user_id,))
            result = cursor.fetchall()
            distraction_patterns = {row[0]: float(row[1]) for row in result if row[0] and row[1] is not None}
            
            # Response history
            cursor.execute('SELECT domain, answer, timestamp FROM intervention_responses WHERE user_id = ? ORDER BY timestamp DESC LIMIT 10', (user_id,))
            result = cursor.fetchall()
            response_history = [{'domain': r[0] or '', 'answer': r[1] or '', 'timestamp': r[2] or ''} for r in result]
            
            # Productivity score (simple: avg of (productive_duration - distraction_duration))
            cursor.execute('''
                SELECT AVG(CASE WHEN is_productive = 1 THEN duration WHEN is_distraction = 1 THEN -duration ELSE 0 END) as score
                FROM usage_data WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()
            productivity_score = float(result[0]) if result and result[0] is not None else 0.0
            
            # Stress indicators (placeholder: based on keywords in answers)
            stress_indicators = []
            for h in response_history:
                answer = h.get('answer', '').lower()
                if any(word in answer for word in ['stressed', 'overwhelmed', 'tired', 'difficult']):
                    stress_indicators.append('high')
                else:
                    stress_indicators.append('low')
            
            return UserContext(
                typical_productive_hours=productive_hours if productive_hours else [9, 10, 11, 12, 13],  # Default
                distraction_patterns=distraction_patterns,
                response_history=response_history,
                productivity_score=productivity_score,
                stress_indicators=stress_indicators
            )
            
        except Exception as e:
            print(f"Error getting user context: {e}")
            # Return default context
            return UserContext(
                typical_productive_hours=[9, 10, 11, 12, 13],
                distraction_patterns={},
                response_history=[],
                productivity_score=0.0,
                stress_indicators=[]
            )
        finally:
            conn.close()

    def get_user_analytics_data(self, user_id: str) -> Dict:
        """Get analytics data for insights"""
        conn = self._get_connection()
        try:
            self._ensure_user_exists(user_id, conn)
            cursor = conn.cursor()
            
            # Total time
            cursor.execute('SELECT SUM(duration) FROM usage_data WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            total_time = int(result[0]) if result and result[0] is not None else 0
            
            # Top distractions
            cursor.execute('''
                SELECT domain, SUM(duration) as total
                FROM usage_data WHERE user_id = ? AND is_distraction = 1
                GROUP BY domain ORDER BY total DESC LIMIT 3
            ''', (user_id,))
            result = cursor.fetchall()
            top_distractions = [row[0] for row in result if row[0]]
            
            return {
                'total_time': total_time,
                'top_distractions': top_distractions
            }
            
        except Exception as e:
            print(f"Error getting user analytics data: {e}")
            return {'total_time': 0, 'top_distractions': []}
        finally:
            conn.close()

    def get_user_performance(self, user_id: str) -> Dict:
        """Get performance data for limit adjustments"""
        conn = self._get_connection()
        try:
            self._ensure_user_exists(user_id, conn)
            cursor = conn.cursor()
            
            # Distraction usage
            cursor.execute('''
                SELECT domain, SUM(duration) as total
                FROM usage_data WHERE user_id = ? AND is_distraction = 1
                GROUP BY domain
            ''', (user_id,))
            result = cursor.fetchall()
            distraction_usage = {row[0]: int(row[1]) for row in result if row[0] and row[1] is not None}
            
            # Productive usage
            cursor.execute('''
                SELECT domain, SUM(duration) as total
                FROM usage_data WHERE user_id = ? AND is_productive = 1
                GROUP BY domain
            ''', (user_id,))
            result = cursor.fetchall()
            productive_usage = {row[0]: int(row[1]) for row in result if row[0] and row[1] is not None}
            
            return {
                'distraction_usage': distraction_usage,
                'productive_usage': productive_usage
            }
            
        except Exception as e:
            print(f"Error getting user performance: {e}")
            return {'distraction_usage': {}, 'productive_usage': {}}
        finally:
            conn.close()

    def update_distraction_limits(self, user_id: str, adjustments: Dict):
        """Update distraction limits"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(user_id, conn)
                cursor = conn.cursor()
                
                for domain, adj in adjustments.items():
                    new_limit = int(adj.get('new_limit', 0))
                    cursor.execute('''
                        INSERT OR REPLACE INTO distraction_limits (user_id, domain, limit_minutes)
                        VALUES (?, ?, ?)
                    ''', (user_id, domain, new_limit))
                
                conn.commit()
                print(f"Updated distraction limits for user {user_id}")
                
            except Exception as e:
                print(f"Error updating distraction limits: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def update_productive_targets(self, user_id: str, adjustments: Dict):
        """Update productive targets"""
        with self.lock:
            conn = self._get_connection()
            try:
                self._ensure_user_exists(user_id, conn)
                cursor = conn.cursor()
                
                for domain, adj in adjustments.items():
                    new_target = int(adj.get('new_target', 0))
                    cursor.execute('''
                        INSERT OR REPLACE INTO productive_targets (user_id, domain, target_minutes)
                        VALUES (?, ?, ?)
                    ''', (user_id, domain, new_target))
                
                conn.commit()
                print(f"Updated productive targets for user {user_id}")
                
            except Exception as e:
                print(f"Error updating productive targets: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def get_daily_data(self, user_id: str, date: str) -> Dict:
        """Get daily data for summary"""
        conn = self._get_connection()
        try:
            self._ensure_user_exists(user_id, conn)
            cursor = conn.cursor()
            
            start_date = f"{date} 00:00:00"
            end_date = f"{date} 23:59:59"
            
            cursor.execute('''
                SELECT url, domain, duration, is_distraction, is_productive
                FROM usage_data 
                WHERE user_id = ? AND timestamp BETWEEN ? AND ?
            ''', (user_id, start_date, end_date))
            
            result = cursor.fetchall()
            usage_entries = []
            for row in result:
                usage_entries.append({
                    'url': row[0] or '',
                    'domain': row[1] or '',
                    'duration': int(row[2]) if row[2] is not None else 0,
                    'is_distraction': bool(row[3]),
                    'is_productive': bool(row[4])
                })
            
            return {'usage_entries': usage_entries}
            
        except Exception as e:
            print(f"Error getting daily data: {e}")
            return {'usage_entries': []}
        finally:
            conn.close()

    def close(self):
        """Close method for compatibility (connections are per-thread now)"""
        pass

    @property
    def cursor(self):
        """
        WARNING: This property is for legacy compatibility only.
        It does not automatically close the connection.
        """
        # If you truly need this, at least ensure the connection is handled correctly
        # But it is better to avoid this property in production code.
        return self._get_connection().cursor()