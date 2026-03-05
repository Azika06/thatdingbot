# database.py
import sqlite3
import os
from datetime import datetime, timedelta
import random
import string
from config import ADMIN_IDS, MODERATOR_IDS

class Database:
    def __init__(self, db_name="dating_bot.db"):
        self.db_name = db_name
        self.init_db()
    
    def get_connection(self):
        return sqlite3.connect(self.db_name)
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    registration_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    is_banned BOOLEAN DEFAULT 0,
                    ban_reason TEXT,
                    ban_date TIMESTAMP,
                    is_admin BOOLEAN DEFAULT 0,
                    is_moderator BOOLEAN DEFAULT 0,
                    invited_by INTEGER,
                    referrals_count INTEGER DEFAULT 0,
                    referal_code TEXT UNIQUE
                )
            ''')
            
            # Таблица анкет
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    show_gender TEXT,
                    city TEXT,
                    description TEXT,
                    photos TEXT,  -- JSON массив с путями к фото
                    is_visible BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица лайков
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user INTEGER,
                    to_user INTEGER,
                    is_mutual BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP,
                    FOREIGN KEY (from_user) REFERENCES users (user_id),
                    FOREIGN KEY (to_user) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица жалоб
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_user INTEGER,
                    to_user INTEGER,
                    complaint_text TEXT,
                    created_at TIMESTAMP,
                    is_resolved BOOLEAN DEFAULT 0,
                    FOREIGN KEY (from_user) REFERENCES users (user_id),
                    FOREIGN KEY (to_user) REFERENCES users (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id, username, first_name, last_name, invited_by=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                return False
            
            # Генерируем реферальный код
            referal_code = self.generate_referal_code()
            
            cursor.execute('''
                INSERT INTO users 
                (user_id, username, first_name, last_name, registration_date, invited_by, referal_code)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, datetime.now(), invited_by, referal_code))
            
            # Обновляем счетчик рефералов у пригласившего
            if invited_by:
                cursor.execute('''
                    UPDATE users SET referrals_count = referrals_count + 1 
                    WHERE user_id = ?
                ''', (invited_by,))
            
            conn.commit()
            return True
    
    def generate_referal_code(self):
        while True:
            code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT user_id FROM users WHERE referal_code = ?", (code,))
                if not cursor.fetchone():
                    return code
    
    def get_user_by_referal_code(self, code):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE referal_code = ?", (code,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_user_username(self, user_id):
        """Получение username пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def save_profile(self, user_id, data):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли анкета
            cursor.execute("SELECT user_id FROM profiles WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                # Обновляем существующую анкету
                cursor.execute('''
                    UPDATE profiles SET
                        name = ?, age = ?, gender = ?, show_gender = ?,
                        city = ?, description = ?, photos = ?, updated_at = ?
                    WHERE user_id = ?
                ''', (
                    data['name'], data['age'], data['gender'], data['show_gender'],
                    data['city'], data['description'], data.get('photos', '[]'),
                    datetime.now(), user_id
                ))
            else:
                # Создаем новую анкету
                cursor.execute('''
                    INSERT INTO profiles
                    (user_id, name, age, gender, show_gender, city, description, photos, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id, data['name'], data['age'], data['gender'], data['show_gender'],
                    data['city'], data['description'], data.get('photos', '[]'),
                    datetime.now(), datetime.now()
                ))
            
            conn.commit()
    
    def get_profile(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, result))
            return None
    
    def update_profile_field(self, user_id, field, value):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE profiles SET {field} = ?, updated_at = ? WHERE user_id = ?", 
                          (value, datetime.now(), user_id))
            conn.commit()
    
    def toggle_profile_visibility(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_visible FROM profiles WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                new_value = not result[0]
                cursor.execute("UPDATE profiles SET is_visible = ? WHERE user_id = ?", 
                              (new_value, user_id))
                conn.commit()
                return new_value
            return None
    
    def get_users_for_search(self, user_id, filters=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT p.* FROM profiles p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.user_id != ? 
                AND p.is_visible = 1 
                AND u.is_active = 1 
                AND u.is_banned = 0
            '''
            params = [user_id]
            
            if filters:
                if filters.get('city'):
                    query += " AND p.city = ?"
                    params.append(filters['city'])
                
                if filters.get('gender'):
                    if filters['gender'] != 'Не важно':
                        query += " AND p.gender = ?"
                        params.append(filters['gender'])
                
                if filters.get('age'):
                    query += " AND p.age BETWEEN ? AND ?"
                    params.append(filters['age'] - 3)
                    params.append(filters['age'] + 3)
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            if results:
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in results]
            return []
    
    def add_like(self, from_user, to_user):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, был ли уже лайк от to_user к from_user
            cursor.execute('''
                SELECT id FROM likes 
                WHERE from_user = ? AND to_user = ?
            ''', (to_user, from_user))
            
            mutual = cursor.fetchone() is not None
            
            # Добавляем лайк
            cursor.execute('''
                INSERT INTO likes (from_user, to_user, is_mutual, created_at)
                VALUES (?, ?, ?, ?)
            ''', (from_user, to_user, mutual, datetime.now()))
            
            # Если взаимный лайк, обновляем оба
            if mutual:
                cursor.execute('''
                    UPDATE likes SET is_mutual = 1 
                    WHERE (from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?)
                ''', (from_user, to_user, to_user, from_user))
            
            conn.commit()
            return mutual
    
    def add_complaint(self, from_user, to_user):
        """Добавление жалобы и проверка на автоматическую блокировку"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Добавляем жалобу
            cursor.execute('''
                INSERT INTO complaints (from_user, to_user, created_at)
                VALUES (?, ?, ?)
            ''', (from_user, to_user, datetime.now()))
            
            conn.commit()
            
            # Проверяем количество жалоб на пользователя
            return self.check_complaints_and_ban(to_user)
    
    def check_complaints_and_ban(self, user_id):
        """Проверка количества жалоб и автоматическая блокировка"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Считаем количество неразрешенных жалоб за последние 7 дней
            seven_days_ago = datetime.now() - timedelta(days=7)
            cursor.execute('''
                SELECT COUNT(*) FROM complaints 
                WHERE to_user = ? 
                AND created_at > ?
                AND is_resolved = 0
            ''', (user_id, seven_days_ago))
            
            complaints_count = cursor.fetchone()[0]
            
            # Если 6 или более жалоб - блокируем
            if complaints_count >= 6:
                self.ban_user(user_id, "Автоматическая блокировка: 6+ жалоб от пользователей")
                return True  # Пользователь заблокирован
            
            # Если 5 жалоб - предупреждение
            elif complaints_count == 5:
                return "warning"  # Нужно отправить предупреждение
            
            return False  # Не заблокирован
    
    def ban_user(self, user_id, reason="Нарушение правил"):
        """Блокировка пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_banned = 1, ban_reason = ?, ban_date = ? 
                WHERE user_id = ?
            ''', (reason, datetime.now(), user_id))
            conn.commit()
    
    def unban_user(self, user_id):
        """Разблокировка пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET is_banned = 0, ban_reason = NULL, ban_date = NULL 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def is_user_banned(self, user_id):
        """Проверка, заблокирован ли пользователь"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else False
    
    def get_user_by_username(self, username):
        """Поиск пользователя по username"""
        if username.startswith('@'):
            username = username[1:]
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_statistics(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            cursor.execute("SELECT COUNT(*) FROM users")
            stats['total_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
            stats['banned_users'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM profiles")
            stats['total_profiles'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM complaints WHERE is_resolved = 0")
            stats['active_complaints'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM complaints")
            stats['total_complaints'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM likes WHERE is_mutual = 1")
            stats['mutual_likes'] = cursor.fetchone()[0]
            
            return stats
    
    def is_admin(self, user_id):
        return user_id in ADMIN_IDS
    
    def is_moderator(self, user_id):
        return user_id in MODERATOR_IDS or user_id in ADMIN_IDS

# Создаем глобальный экземпляр БД
db = Database()