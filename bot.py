import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
import os
import sys
import time
from datetime import datetime, timedelta

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN, ANONYM_BOT_LINK, ADMIN_IDS, MODERATOR_IDS
from database import db
from utils.keyboards import *
from utils.helpers import *
import handlers.registration as registration
import handlers.main_menu as main_menu
import handlers.profile as profile
import handlers.search as search
import handlers.admin as admin

# Инициализация бота
bot = telebot.TeleBot(TOKEN)

# Словарь для хранения временных данных пользователей
user_data = {}

def set_bot_commands():
    """Установка команд бота с разными правами доступа"""
    
    # Команды для всех пользователей (по умолчанию)
    default_commands = [
        BotCommand("start", "Запустить бота / Главное меню")
    ]
    
    # Устанавливаем команды по умолчанию для всех
    bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    
    # Устанавливаем дополнительные команды для каждого администратора отдельно
    all_admins = ADMIN_IDS + MODERATOR_IDS
    
    for admin_id in all_admins:
        try:
            # Команды для конкретного администратора
            admin_commands = [
                BotCommand("start", "Запустить бота / Главное меню"), 
                BotCommand("admin", "Админ панель")
            ]
            
            # Устанавливаем команды для конкретного чата (администратора)
            bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
            print(f"Команды установлены для админа {admin_id}")
        except Exception as e:
            print(f"Ошибка при установке команд для админа {admin_id}: {e}")

def welcome_keyboard(is_admin=False):
    """Клавиатура для приветственного сообщения"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("Анонимно", url=ANONYM_BOT_LINK),
        InlineKeyboardButton("Оформить", callback_data="start_registration")
    ]
    
    # Добавляем кнопку админ панели для администраторов
    if is_admin:
        keyboard.add(InlineKeyboardButton("Админ панель", callback_data="admin_panel"))
    
    keyboard.add(*buttons)
    return keyboard

def get_user_ban_info(user_id):
    """Получение информации о блокировке"""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ban_reason, ban_date FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        
        if result and result[0]:
            ban_date = result[1][:10] if result[1] else 'Неизвестно'
            ban_reason = result[0]
            
            text = f"⛔️ Ты заблокирован. Причина: {ban_reason}. Дата: {ban_date}"
            return text
        else:
            return "⛔️ Ты заблокирован"

# ================== КОМАНДЫ ==================

@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработка команды /start"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, заблокирован ли пользователь
        if db.is_user_banned(user_id):
            ban_info = get_user_ban_info(user_id)
            bot.reply_to(message, ban_info, reply_markup=support_only_keyboard())
            return
        
        username = message.from_user.username
        first_name = message.from_user.first_name
        last_name = message.from_user.last_name
        
        # Проверка наличия username
        if not username:
            bot.reply_to(message, "⚠️ Для использования бота необходимо иметь username в Telegram.\n\n"
                         "Настройки → Изменить профиль → Username")
            return
        
        # Проверяем реферальный код
        invited_by = None
        if len(message.text.split()) > 1:
            ref_code = message.text.split()[1]
            invited_by = db.get_user_by_referal_code(ref_code)
        
        # Регистрируем пользователя
        db.add_user(user_id, username, first_name, last_name, invited_by)
        
        # Проверяем, есть ли у пользователя анкета
        profile_exists = db.get_profile(user_id)
        
        # Проверяем, является ли пользователь администратором
        is_admin = db.is_admin(user_id) or db.is_moderator(user_id)
        
        if profile_exists:
            # Приветственное сообщение для пользователя с анкетой
            welcome_text = (
                "👋 С возвращением!\n\n"
                "Рад видеть тебя снова! Твоя анкета уже создана. Ты можешь перейти на главное меню или начать анонимное общение."
            )
            
            keyboard = InlineKeyboardMarkup(row_width=2)
            buttons = [
                InlineKeyboardButton("Анонимно", url=ANONYM_BOT_LINK),
                InlineKeyboardButton("Главное меню", callback_data="main_menu")
            ]
            
            # Добавляем кнопку админ панели для администраторов
            if is_admin:
                keyboard.add(InlineKeyboardButton("Админ панель", callback_data="admin_panel"))
            
            keyboard.add(*buttons)
            
        else:
            # Приветственное сообщение для нового пользователя
            welcome_text = (
                "👋 Добро пожаловать к нам!\n\n"
                "Ты можешь начать оформление анкеты или если не хочешь "
                "раскрывать свою личность и остаться анонимом - можешь "
                "перейти на нашего бота для анонимного общения."
            )
            
            keyboard = InlineKeyboardMarkup(row_width=2)
            buttons = [
                InlineKeyboardButton("Анонимно", url=ANONYM_BOT_LINK),
                InlineKeyboardButton("Оформить", callback_data="start_registration")
            ]
            
            # Добавляем кнопку админ панели для администраторов
            if is_admin:
                keyboard.add(InlineKeyboardButton("Админ панель", callback_data="admin_panel"))
            
            keyboard.add(*buttons)
        
        bot.send_message(message.chat.id, welcome_text, reply_markup=keyboard, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Ошибка в команде start: {e}")
        bot.reply_to(message, "Произошла ошибка. Пожалуйста, попробуй позже.")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    """Команда для входа в админ панель"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, заблокирован ли пользователь
        if db.is_user_banned(user_id):
            bot.reply_to(message, get_user_ban_info(user_id), reply_markup=support_only_keyboard())
            return
        
        if db.is_admin(message.from_user.id) or db.is_moderator(message.from_user.id):
            admin.show_admin_panel(bot, message.chat.id, message.message_id)
        else:
            bot.send_message(message.chat.id, "У тебя нет доступа к этой функции.")
    except Exception as e:
        print(f"Ошибка в команде admin: {e}")
        bot.reply_to(message, "Произошла ошибка. Пожалуйста, попробуй позже.")

# ================== ОБРАБОТКА КНОПОК ==================

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    """Обработка нажатий на инлайн кнопки"""
    try:
        user_id = call.from_user.id
        
        # Проверяем, заблокирован ли пользователь
        if db.is_user_banned(user_id):
            bot.answer_callback_query(call.id, "Вы заблокированы")
            bot.send_message(call.message.chat.id, get_user_ban_info(user_id), reply_markup=support_only_keyboard())
            return
        
        data = call.data
        
        # Обработка кнопки начала регистрации из приветствия
        if data == "start_registration":
            # Проверяем наличие username
            username = call.from_user.username
            if not username:
                bot.answer_callback_query(call.id, "Необходимо иметь username в Telegram")
                bot.send_message(call.message.chat.id, 
                               "⚠️ Для использования бота необходимо иметь username в Telegram.\n\n"
                               "Настройки → Изменить профиль → Username")
                return
            
            # Проверяем, есть ли уже анкета
            profile_exists = db.get_profile(user_id)
            if profile_exists:
                bot.answer_callback_query(call.id, "У тебя уже есть анкета!")
                main_menu.show_main_menu(bot, call.message.chat.id)
            else:
                bot.delete_message(call.message.chat.id, call.message.message_id)
                registration.start_registration(bot, call.message.chat.id, user_id, user_data)
            return
        
        # Обработка кнопок регистрации
        if data in ['take_from_profile', 'skip', 'gender_male', 'gender_female', 
                     'gender_other', 'show_male', 'show_female', 'show_all',
                     'save_profile', 'restart_registration']:
            registration.handle_registration_callback(bot, call, user_data)
            return
        
        # Обработка кнопок главного меню
        if data in ['main_menu', 'search_menu', 'my_profile', 'toggle_profile',
                     'referral', 'info', 'anon_chat']:
            main_menu.handle_main_menu_callback(bot, call, user_data)
            return
        
        # Обработка кнопок поиска
        if data in ['search_city', 'search_gender', 'search_age', 'search_all',
                     'search_random', 'next_profile']:
            search.handle_search_callback(bot, call, user_data)
            return
        
        # Обработка кнопок профиля
        if data in ['edit_profile', 'delete_profile', 'confirm_delete', 'edit_name', 
                    'edit_age', 'edit_gender', 'edit_city', 'edit_description', 
                    'edit_photos', 'edit_take_name', 'edit_take_photos']:
            profile.handle_profile_callback(bot, call, user_data)
            return
        
        # Обработка лайков и жалоб
        if data.startswith('like_') or data.startswith('complaint_') or data.startswith('show_liker_'):
            search.handle_interaction_callback(bot, call, user_data)
            return
        
        # Обработка админ кнопок
        admin_buttons = ['admin_panel', 'admin_stats', 'admin_mailing', 'admin_download_stats',
                         'mailing_text', 'mailing_photo', 'send_mailing', 'admin_ban_menu',
                         'admin_ban', 'admin_unban', 'admin_back']
        
        if data in admin_buttons:
            if db.is_admin(user_id) or db.is_moderator(user_id):
                admin.handle_admin_callback(bot, call, user_data)
            else:
                bot.answer_callback_query(call.id, "У тебя нет доступа")
            return
        
        # Если кнопка не обработана, просто отвечаем на callback
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Ошибка обработки callback: {e}")
        try:
            bot.answer_callback_query(call.id, "Произошла ошибка")
        except:
            pass

# ================== ОБРАБОТКА ТЕКСТА ==================

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    """Обработка текстовых сообщений"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, заблокирован ли пользователь
        if db.is_user_banned(user_id):
            bot.reply_to(message, get_user_ban_info(user_id), reply_markup=support_only_keyboard())
            return
        
        chat_id = message.chat.id
        
        # Проверяем, находится ли пользователь в процессе регистрации
        if user_id in user_data and 'registration_step' in user_data[user_id]:
            registration.handle_registration_input(bot, message, user_data)
            return
        
        # Проверяем, находится ли пользователь в процессе редактирования профиля
        if user_id in user_data and 'edit_step' in user_data[user_id]:
            profile.handle_edit_input(bot, message, user_data)
            return
        
        # Проверяем, находится ли администратор в процессе рассылки или бана
        if user_id in user_data:
            if 'mailing_step' in user_data[user_id]:
                admin.handle_mailing_input(bot, message, user_data)
                return
            elif 'ban_step' in user_data[user_id]:
                admin.handle_ban_input(bot, message, user_data)
                return
        
        # Если ничего не выбрано, отправляем в главное меню
        main_menu.show_main_menu(bot, chat_id)
    except Exception as e:
        print(f"Ошибка обработки текста: {e}")
        bot.reply_to(message, "Произошла ошибка. Пожалуйста, попробуй позже.")

# ================== ОБРАБОТКА ФАЙЛОВ ==================

@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    """Обработка фото и видео"""
    try:
        user_id = message.from_user.id
        
        # Проверяем, заблокирован ли пользователь
        if db.is_user_banned(user_id):
            bot.reply_to(message, get_user_ban_info(user_id), reply_markup=support_only_keyboard())
            return
        
        # Проверяем, находится ли пользователь в процессе загрузки фото для анкеты
        if user_id in user_data:
            if 'registration_step' in user_data[user_id]:
                registration.handle_photo_upload(bot, message, user_data)
                return
            elif 'edit_step' in user_data[user_id]:
                profile.handle_photo_edit(bot, message, user_data)
                return
            elif 'mailing_step' in user_data[user_id]:
                admin.handle_mailing_photo(bot, message, user_data)
                return
        
        # Если пользователь не в процессе регистрации или редактирования
        bot.reply_to(message, "Пожалуйста, используй кнопки для навигации.")
    except Exception as e:
        print(f"Ошибка обработки медиа: {e}")
        bot.reply_to(message, "Произошла ошибка при загрузке файла.")

# Функция для периодической очистки трекера лайков
def cleanup_likes_tracker():
    """Очистка старых записей из трекера лайков"""
    while True:
        try:
            current_time = datetime.now()
            users_to_remove = []
            
            for user_id, tracker in search.user_likes_tracker.items():
                # Проверяем, не истек ли мут
                if 'muted_until' in tracker:
                    if current_time >= tracker['muted_until']:
                        users_to_remove.append(user_id)
                    continue
                
                # Очищаем старые лайки (старше 1 часа)
                one_hour_ago = current_time - timedelta(hours=1)
                tracker['likes'] = [t for t in tracker['likes'] if t > one_hour_ago]
                
                # Если нет лайков за последний час, удаляем пользователя
                if not tracker['likes']:
                    users_to_remove.append(user_id)
            
            # Удаляем пользователей
            for user_id in users_to_remove:
                if user_id in search.user_likes_tracker:
                    del search.user_likes_tracker[user_id]
            
            # Запускаем очистку каждый час
            time.sleep(3600)
        except Exception as e:
            print(f"Ошибка в cleanup_likes_tracker: {e}")
            time.sleep(3600)

# Запускаем очистку в отдельном потоке
import threading
cleanup_thread = threading.Thread(target=cleanup_likes_tracker, daemon=True)
cleanup_thread.start()

# ================== ЗАПУСК БОТА ==================

if __name__ == '__main__':
    print("Бот запущен...")
    ensure_photos_dir()
    set_bot_commands()  # Устанавливаем команды бота
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(5)