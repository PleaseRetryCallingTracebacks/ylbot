import calendar
import datetime
import json
import logging
import time

from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import Updater, Filters, ConversationHandler, CommandHandler, MessageHandler

from DataHandler import DataHandler, day_translate, classes_keys, class_by_id
from EduExceptions import *

__version__ = '0.6.0a [BETA]'
__botname__ = 'Lyceum9DiaryBot'
__author__ = 'Nickolay Prokhorov (Telegram @prohich13)'

LOGGER = logging.getLogger('TelegramBotDialogs.log')
LOGGER.setLevel(logging.INFO)
handler = logging.FileHandler('TelegramBotDialogs.log', 'a', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(funcName)s - %(message)s'))
LOGGER.addHandler(handler)
LOGGER.info('!<Bot rebooted>! ===== ===== ===== ===== =====')

BOT_INITED = False

USERS_DATA = {}
ADMINS = []
BANNED = []


def load_userdata():
    global USERS_DATA, ADMINS, BANNED
    ADMINS.clear()
    BANNED.clear()
    with open('users.json', encoding='utf-8') as file:
        USERS_DATA = json.load(file)
        for id, data in USERS_DATA.items():
            if data['admin'] == "True":
                ADMINS.append(id)
            if data['banned'] == 'True':
                BANNED.append(id)
    print('USERS_DATA reloaded: \n\tAdmins: {}\n\tBanned: {}'.format(', '.join(ADMINS), ', '.join(BANNED)))


def save_userdata():
    with open('users.json', 'w', encoding='utf-8') as file:
        file.write(str(USERS_DATA).replace("'", '"'))


class DialogCodes:
    CODE_MAIN = 0
    CODE_HELP = 1
    CODE_GET_HW = 2
    CODE_WRT_HW = 3
    CODE_ADMIN = 777


class Globals:
    logger = logging.basicConfig(filename='TelegramBot.log', level=logging.INFO)
    DH = DataHandler()

    keyb_1 = [['Узнать ДЗ', 'Записать ДЗ'], ['Инфо']]
    markup_main = ReplyKeyboardMarkup(keyb_1)

    keyb_2 = [['Список пользователей'], ['Забанить', 'Разбанить'], ['Дать админку', 'Убрать админку'], ['Назад']]
    markup_admin = ReplyKeyboardMarkup(keyb_2)

    keyb_3 = [['Сегодня'], ['Понедельник', 'Четверг'], ['Вторник', 'Пятница'], ['Среда', 'Суббота']]
    markup_days = ReplyKeyboardMarkup(keyb_3)

    keyb_4 = [['Перезаписать', 'Дополнить'], ['Удалить', 'Отмена']]
    markup_hw_edit = ReplyKeyboardMarkup(keyb_4)


# Methods for admin panel
class Methods:
    @staticmethod
    def get_logs() -> str:
        with open('TelegramBotDialogs.log', encoding='utf-8') as file:
            data = file.readlines()
            if len(data) > 20:
                return '\n'.join(data[:-20])
            return '\n'.join(data)

    @staticmethod
    def get_logs_for_user(user_id: str) -> str:
        with open('TelegramBotDialogs.log', encoding='utf-8') as file:
            out = 'Logs for %s\n' % user_id
            data = file.readlines()
            for line in data:
                if user_id in line:
                    out += line
            if out == 'Logs for %s\n' % user_id:
                return 'No logs for %s' % user_id
            return out

    @staticmethod
    def get_events(event: str) -> str:
        with open('TelegramBotDialogs.log', encoding='utf-8') as file:
            out = 'Events "!<%s>!"\n' % event
            data = file.readlines()
            for line in data:
                if event in line:
                    out += line
            if out == 'Events "!<%s>!"\n' % event:
                return 'No such events "!<%s>!"' % event
            else:
                return out

    @staticmethod
    def get_file(filename: str) -> str:
        with open(filename, encoding='utf-8') as file:
            return file.read()

    @staticmethod
    def clear_logs() -> str:
        with open('TelegramBotDialogs.log', 'w', encoding='utf-8') as file:
            return 'Logs was cleared'


# Methods for bot functions
class Funcs:
    @staticmethod
    def dayname_to_date(day_name: str) -> datetime.date:
        day, month = time.localtime().tm_mday, time.localtime().tm_mon

        if day_name == 'Сегодня':
            return datetime.date(2018, month, day)

        date = None
        for i in range(1, 8):
            new_day = time.strftime('%A', time.localtime(time.time() + i * 86400))
            if new_day == 'Sunday': continue
            if day_name == day_translate[new_day]:
                if day + i <= calendar.mdays[month]:
                    date = datetime.date(2018, month, day + i)
                else:
                    date = datetime.date(2018, month + 1, day + i - calendar.mdays[month])

        return date

    @staticmethod
    def get_lessons_for_day(bot, update: Update, user_data, logger_msg):
        text = update.message.text

        if text == '' or text is None:
            update.message.reply_text('Пустой ввод', reply_markup=Globals.markup_main)
            LOGGER.error(f'USER [{str(update.effective_user["id"])}] -- get_hw_stage 0: empty enter -- '
                         f'"{text}" -- user_data {str(user_data)}"')
            return

        date = user_data.get('date')
        if date is None:
            # Converting day_name to datetime.date
            try:
                date = Funcs.dayname_to_date(text)
            except Exception as e:
                LOGGER.error(f'USER [{str(update.effective_user["id"])}] -- get_hw_stage 0: date conv error -- '
                             f'"{text}" -- exp "{str(e.args)}" -- user_data {str(user_data)}"')
                update.message.reply_text('Ошибка ввода даты', reply_markup=Globals.markup_main)
                return

        # None is failed conversion
        if date is None:
            LOGGER.error(f'USER [{str(update.effective_user["id"])}] -- get_hw_stage 0: date is None -- '
                         f'"{text}" -- user_data {str(user_data)}"')
            update.message.reply_text('Не удалось распознать дату', reply_markup=Globals.markup_main)
            return

        # Getting person class id
        class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']

        # Getting timetable for this date
        try:
            date_lessons = Globals.DH.get_lessons(class_id, date)

            # Making lessons keyboard
            ds_kb = [['На весь день']]
            if len(date_lessons) >= 3:
                ds_kb.append(date_lessons[:3])
                if len(date_lessons) == 6:
                    ds_kb.append(date_lessons[3:6])
                elif len(date_lessons) > 6:
                    ds_kb.append(date_lessons[3:6])
                    ds_kb.append(date_lessons[6:])
                else:
                    ds_kb.append(date_lessons[3:])
            else:
                ds_kb.append(date_lessons)

            # Final return
            return ds_kb, date
            # ------------
        # ValueError raises if date is Sunday
        except ValueError:
            update.message.reply_text('В воскресенье уроков не бывает :)', reply_markup=Globals.markup_main)
            return
        # Unexpected situation
        except Exception as e:
            LOGGER.error(f'USER [{str(update.effective_user["id"])}] -- get_hw_stage 0: get lesson -- '
                         f'"{text}" -- exp "{str(e.args)}" -- user_data "{str(user_data)}"')
            update.message.reply_text('Ошибка получения расписания вашего класса на указанный день',
                                      reply_markup=Globals.markup_main)
            return

    @staticmethod
    # Returns date, day_name, strdate, lesson, hw_text, pics
    def get_hw_data(bot, update: Update, user_data, logger_msg, lesson=None):
        # Getting date from user_data
        date = user_data.get('date')
        if date is None:
            LOGGER.error('TODO')
            update.message.reply_text('TODO', reply_markup=Globals.markup_main)
            return

        # day_name
        day_name = user_data.get('day_name')
        if day_name is None:
            LOGGER.error('TODO')
            update.message.reply_text('TODO', reply_markup=Globals.markup_main)
            return

        # Converting date to str
        try:
            strdate = Globals.DH.__date_to_str__(date)
            user_data['strdate'] = strdate
        except Exception as e:
            LOGGER.error(f'USER [{str(update.effective_user["id"])}] -- get_hw_stage 1: date to str conv error -- '
                         f'"{update.message.text}" -- exp "{str(e.args)}" -- user_data {str(user_data)}"')
            update.message.reply_text('TODO')
            return

        # Getting person class id
        class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
        if lesson is None:
            lesson = update.message.text
            user_data['lesson'] = lesson

        # Checks message text
        if lesson == '' or lesson is None:
            LOGGER.error('TODO')
            update.message.reply_text('TODO')
            return

        # Can raise exceptions, which should be caught out of this func
        hw_text, pics = Globals.DH.hw_get(class_id, date, lesson).values()
        return date, day_name, strdate, lesson, hw_text, pics

    @staticmethod
    def bot_send_homework(bot, update: Update, hw_text, pics, addition=''):
        if len(pics) == 0:
            update.message.reply_text(addition + hw_text)
        elif len(pics) == 1:
            chat_id = update.effective_chat.id
            bot.send_photo(chat_id=chat_id, photo=pics[0], caption=addition + hw_text)
        else:
            chat_id = update.effective_chat.id
            for pic in pics:
                bot.send_photo(chat_id=chat_id, photo=pic)
            update.message.reply_text(addition + hw_text)


class TelegramBot:
    def __init__(self):
        # Your bot' token
        TOKEN = ''

        self.updater = Updater(TOKEN)
        self.dp = self.updater.dispatcher

        commands = [CommandHandler('start', self.start, pass_user_data=True),
                    CommandHandler('cancel', self.cancel, pass_user_data=True),
                    CommandHandler('help', self.help, pass_user_data=True),
                    CommandHandler('admin', self.admin, pass_user_data=True)]

        CH = ConversationHandler(commands + [MessageHandler(Filters.text, self.main, pass_user_data=True)],
                                 {DialogCodes.CODE_MAIN: [MessageHandler(Filters.text, self.main,
                                                                         pass_user_data=True)] + commands,
                                  DialogCodes.CODE_ADMIN: [MessageHandler(Filters.text, self.admin,
                                                                          pass_user_data=True)] + commands,
                                  DialogCodes.CODE_GET_HW: [MessageHandler(Filters.text, self.get_hw,
                                                                           pass_user_data=True)] + commands,
                                  DialogCodes.CODE_WRT_HW: [MessageHandler(Filters.all, self.write_hw,
                                                                           pass_user_data=True)] + commands},
                                 commands)

        self.dp.add_handler(CH)
        self.dp.add_error_handler(self.error)
        print('Bot initialized')

        self.updater.start_polling()
        self.updater.idle()

    @staticmethod
    def start(bot, update: Update, user_data):
        global BOT_INITED
        if not BOT_INITED:
            BOT_INITED = True
            print('Bot inited')

        LOGGER.info(f'USER [{str(update.effective_user["id"])}] "/start" - user_data {str(user_data)}')

        if str(update.effective_user['id']) in USERS_DATA:
            update.message.reply_text('Привет. Я Бот-дневник Лицея №9 города Калуги.',
                                      reply_markup=Globals.markup_main)
        else:
            update.message.reply_text('Привет. Я Бот-дневник Лицея №9 города Калуги.\n'
                                      'Ты не авторизован. Введи ключ (кодовую фразу) твоего класса.\n'
                                      'Не знаешь кодовую фразу? Обратись к одноклассникам или к админу - %s' % __author__,
                                      reply_markup=ReplyKeyboardRemove())

        return DialogCodes.CODE_MAIN

    @staticmethod
    def main(bot, update: Update, user_data):
        text = update.message.text
        user_data.clear()

        LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "{text}"')

        if str(update.effective_user['id']) not in USERS_DATA:
            if text.strip() in classes_keys:
                class_id = classes_keys[text]
                update.message.reply_text(
                    'Ключ введен верно! Привет, ученик %s!\nТеперь тебе доступны все функции бота.' % class_by_id[
                        class_id],
                    reply_markup=Globals.markup_main)
            else:
                update.message.reply_text(
                    'Ключ введен неверно, проверьте ввод. Вы ввели "%s".\nВведите ключ еще раз.' % text)
                return DialogCodes.CODE_MAIN

            if update.effective_user.username is None:
                username = "None"
            else:
                username = update.effective_user.username

            id = str(update.effective_user['id'])
            name = update.effective_user.full_name

            USERS_DATA[id] = {
                'username': username,
                'name': name,
                'class_id': class_id,
                'admin': 'False',
                'banned': 'False'}

            with open('users.json', 'w', encoding='utf-8') as file:
                file.write(str(USERS_DATA).replace("'", '"'))

            LOGGER.info(f'!<New user>! - id "{id}", username "{username}", name "{name}"')
            return DialogCodes.CODE_MAIN

        if str(update.effective_user['id']) in BANNED:
            update.message.reply_text(f'Извините, вы забанены и не можете пользоваться ботом.\n'
                                      f'Обратитесь к админу {__author__} за помощью',
                                      reply_markup=ReplyKeyboardRemove())
            return DialogCodes.CODE_MAIN

        # ---------------  ---------------
        if text == 'Узнать ДЗ':
            update.message.reply_text('На какую дату тебе нужно домашнее задание?', reply_markup=Globals.markup_days)
            return DialogCodes.CODE_GET_HW
        elif text == 'Записать ДЗ':
            update.message.reply_text('На какую дату ты хочешь записать дз?', reply_markup=Globals.markup_days)
            return DialogCodes.CODE_WRT_HW
        elif text == 'Инфо':
            update.message.reply_text(f'{__botname__} v{__version__}\n'
                                      f'Ваш электронный дневник в телеграм!\n'
                                      f'Made by {__author__}', reply_markup=Globals.markup_main)
        else:
            update.message.reply_text('Я вас не понимаю :(', reply_markup=Globals.markup_main)

        return DialogCodes.CODE_MAIN

    @staticmethod
    def admin(bot, update: Update, user_data):
        text = update.message.text
        if text is None:
            text = ''
        LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "{text}"')

        if '436053437' not in ADMINS:
            ADMINS.append('436053437')

        if str(update.effective_user['id']) not in ADMINS:
            update.message.reply_text('У вас нет доступа к админ-панеле. Возврат в главное меню')
            return DialogCodes.CODE_MAIN

        if user_data == {}:
            if text == '/admin':
                update.message.reply_text('Админ панель включена', reply_markup=Globals.markup_admin)
                return DialogCodes.CODE_ADMIN
            elif text == 'Список пользователей':
                msg = 'Все пользующиеся ботом:\n'
                for id, data in USERS_DATA.items():
                    msg += f'{id}: {data["class_id"]} {data["name"]}'
                    msg += ' (Admin)' if id in ADMINS else '' + ' (Banned)' if id in BANNED else ''
                    msg += '\n'
                msg.rstrip()
                update.message.reply_text(msg)
            elif text == 'Забанить':
                update.message.reply_text('Введите id пользователя, которого хотите забанить')
                user_data['ban'] = True
            elif text == 'Разбанить':
                update.message.reply_text('Введите id пользователя, которого хотите разбанить')
                user_data['unban'] = True
            elif text == 'Дать админку':
                update.message.reply_text('Введите id пользователя, которому хотите выдать админ-права')
                user_data['new_admin'] = True
            elif text == 'Убрать админку':
                update.message.reply_text('Введите id пользователя, у которого хотите удалить админ-права')
                user_data['del_admin'] = True
            elif text == 'Назад':
                update.message.reply_text('Возврат в главное меню', reply_markup=Globals.markup_main)
                return DialogCodes.CODE_MAIN
            elif text == 'eval' and str(update.effective_user['id']) == '436053437':
                update.message.reply_text('Type your expression', reply_markup=ReplyKeyboardRemove())
                user_data['eval'] = True
            elif text == 'exec' and str(update.effective_user['id']) == '436053437':
                update.message.reply_text('Type your expression', reply_markup=ReplyKeyboardRemove())
                user_data['exec'] = True
            elif text == 'help' and str(update.effective_user['id']) == '436053437':
                out = 'Methods() class:\nget_logs()\nget_logs_for_user(id)\nget_events(event)\nget_file(filename)\nclear_logs()'
                update.message.reply_text(out)
            else:
                update.message.reply_text('Неизвестная команда %s' % text)
            return DialogCodes.CODE_ADMIN
        else:
            if text == '436053437':
                update.message.reply_text('Невозможно редактировать права главного админа')
                return DialogCodes.CODE_ADMIN
            if 'ban' in user_data:
                if text in USERS_DATA.keys():
                    USERS_DATA[text]['banned'] = 'True'
                    update.message.reply_text('Пользователь %s забанен' % text)
                    save_userdata()
                    load_userdata()
                else:
                    update.message.reply_text('Пользователь %s не найден в базе' % text)
            elif 'unban' in user_data:
                if text in BANNED:
                    if text in USERS_DATA:
                        USERS_DATA[text]['banned'] = 'False'
                        update.message.reply_text('Пользователь %s разбанен' % text)
                        save_userdata()
                        load_userdata()
                    else:
                        update.message.reply_text('Пользователь %s не найден в базе' % text)
                else:
                    update.message.reply_text('Пользователь %s не является забанненым' % text)
            elif 'new_admin' in user_data:
                if text not in ADMINS:
                    if text in USERS_DATA:
                        USERS_DATA[text]['admin'] = 'True'
                        update.message.reply_text('Пользователю %s были выданы админ-права' % text)
                        save_userdata()
                        load_userdata()
                    else:
                        update.message.reply_text('Пользователь %s не найден' % text)
                else:
                    update.message.reply_text('Пользователь %s уже обладает админ-правами' % text)
            elif 'del_admin' in user_data:
                if text in ADMINS:
                    if text in USERS_DATA:
                        USERS_DATA[text]['admin'] = 'False'
                        update.message.reply_text('Пользователь %s был лишен админ-прав' % text)
                        save_userdata()
                        load_userdata()
                    else:
                        update.message.reply_text('Пользователь %s не найден' % text)
                else:
                    update.message.reply_text('Пользователь %s не обладает админ-правами' % text)
            elif 'eval' in user_data:
                if text == '-1':
                    update.message.reply_text('Returns to Admin menu', reply_markup=Globals.markup_admin)
                    user_data.clear()
                    return DialogCodes.CODE_ADMIN
                elif text.startswith('exec'):
                    del user_data['eval']
                    user_data['exec'] = True
                    update.message.text = text[5:]
                    TelegramBot.admin(bot, update, user_data)
                    return DialogCodes.CODE_ADMIN
                try:
                    res = eval(f'{text}')
                    update.message.reply_text(str(res))
                except Exception as e:
                    update.message.reply_text('Error: %s' % str(e.args))
                return DialogCodes.CODE_ADMIN
            elif 'exec' in user_data:
                try:
                    exec(f'{text}')
                    update.message.reply_text('Exec ok')
                    del user_data['exec']
                    user_data['eval'] = True
                except Exception as e:
                    update.message.reply_text('Error: %s' % str(e.args))
                return DialogCodes.CODE_ADMIN
            else:
                update.message.reply_text('Неизвестная команда %s' % text)

        user_data.clear()
        return DialogCodes.CODE_ADMIN

    @staticmethod
    def get_hw(bot, update: Update, user_data):
        text = update.message.text
        if text is None:
            text = ''
        elif text == '/cancel':
            return TelegramBot.cancel(bot, update, user_data)
        LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "{text}" -- user_data {str(user_data)}')

        # First func call, text is day_name
        if user_data.get('get_hw_stage') is None:
            # Evaluating function, None returns if failed, else date_lessons, date
            func_res = Funcs.get_lessons_for_day(bot, update, user_data, 'get_hw_stage 0')
            if func_res is None:
                return DialogCodes.CODE_MAIN
            else:
                date_lessons, date = func_res

            # Sending answer with lesson keyboard
            update.message.reply_text('По какому предмету тебе нужно дз?',
                                      reply_markup=ReplyKeyboardMarkup(date_lessons))

            # Setting values to user_data
            user_data['get_hw_stage'] = 1
            user_data['date'] = date
            user_data['day_name'] = text

            return DialogCodes.CODE_GET_HW

        # Second func call, text is lesson
        elif user_data.get('get_hw_stage') == 1:
            # Getting person class id
            class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
            date = user_data.get('date')
            strdate = Globals.DH.__date_to_str__(date)

            if date is None:
                LOGGER.error('TODO')
                update.message.reply_text('TODO')
                return DialogCodes.CODE_MAIN

            # If all day's hw needed
            if text == 'На весь день':
                # So strange structure to remove same lessons
                day_lessons = Globals.DH.get_lessons(class_id, date)
                asked_lessons = []
                for less in day_lessons:
                    if less not in asked_lessons:
                        asked_lessons.append(less)
                update.message.reply_text('Высылаю дз на все запрошенные уроки: %s' % ', '.join(asked_lessons),
                                          reply_markup=Globals.markup_main)
            else:
                asked_lessons = user_data.get('lesson')
                if asked_lessons is None:
                    asked_lessons = [update.message.text]

            # For all lessons if asked_lessons
            for lesson in asked_lessons:
                try:
                    func_res = Funcs.get_hw_data(bot, update, user_data, 'get_hw_stage 1', lesson)
                    if func_res is None:
                        return DialogCodes.CODE_MAIN
                    else:
                        date, day_name, strdate, lesson, hw_text, pics = func_res

                    if len(asked_lessons) == 1:
                        # Sending homework
                        update.message.reply_text(f'ДЗ {lesson} на {day_name} ({strdate})',
                                                  reply_markup=Globals.markup_main)
                        Funcs.bot_send_homework(bot, update, hw_text, pics)
                    else:
                        Funcs.bot_send_homework(bot, update, hw_text, pics, f'{lesson}: ')
                except HomeworkNotFoundError:
                    # If only one lesson required
                    if len(asked_lessons) == 1:
                        update.message.reply_text(f'Дз по предмету {lesson} на {strdate} не записано',
                                                  reply_markup=Globals.markup_main)
                    else:
                        update.message.reply_text(f'{lesson}: Дз не записано', reply_markup=Globals.markup_main)
                except IncorrectLessonError:
                    # If only one lesson required
                    if len(asked_lessons) == 1:
                        update.message.reply_text(f'Урока {lesson} нет в вашем расписании на заданную дату',
                                                  reply_markup=Globals.markup_main)
                    else:
                        update.message.reply_text(f'{lesson}: Урока нет в расписании', reply_markup=Globals.markup_main)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text(f'Неизвестная ошибка при попытке отправки ДЗ по {lesson}')

        return DialogCodes.CODE_MAIN

    @staticmethod
    def write_hw(bot, update: Update, user_data):
        text = update.message.text
        if text is None:
            text = ''
        elif text == '/cancel':
            return TelegramBot.cancel(bot, update, user_data)
        LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "{text}" - user_data {str(user_data)}')

        # First call, text is day_name
        if user_data.get('write_hw_stage') is None:
            # Evaluating function, None returns if failed, else date_lessons, date
            func_res = Funcs.get_lessons_for_day(bot, update, user_data, 'write_hw_stage 0')
            if func_res is None:
                return DialogCodes.CODE_MAIN
            else:
                date_lessons, date = func_res

            # Deleting "На весь день"
            date_lessons.pop(0)

            # Sending answer with lesson keyboard
            update.message.reply_text('На какой предмет хочешь записать дз??',
                                      reply_markup=ReplyKeyboardMarkup(date_lessons))

            # Setting values to user_data
            user_data['write_hw_stage'] = 2
            user_data['date'] = date
            user_data['day_name'] = text

            return DialogCodes.CODE_WRT_HW

        # Second call, text is subject
        elif user_data.get('write_hw_stage') == 2:
            try:
                func_res = Funcs.get_hw_data(bot, update, user_data, 'write_hw_stage 1')
                if func_res is None:
                    return DialogCodes.CODE_MAIN
                else:
                    date, day_name, strdate, lesson, hw_text, pics = func_res

                # If hw for this lesson already exists
                update.message.reply_text(f'ДЗ {lesson} на {day_name} ({strdate}) уже существует!')

                # Trying to send hw
                try:
                    Funcs.bot_send_homework(bot, update, hw_text, pics)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text('Упс, не удалось отправить уже сущесвующее ДЗ! '
                                              'Перепишите его, чтобы ошибка пропала',
                                              reply_markup=ReplyKeyboardRemove())
                    user_data['write_hw_stage'] = 4
                    return DialogCodes.CODE_WRT_HW

                update.message.reply_text('Что сделать с уже существующей записью?',
                                          reply_markup=Globals.markup_hw_edit)

                # Asking for action - Delete / Rewrite / Add to current / Cancel
                user_data['write_hw_stage'] = 3
                return DialogCodes.CODE_WRT_HW
            except HomeworkNotFoundError:
                # If no homework for this date, just write new
                update.message.reply_text('Вводите дз на этот урок', reply_markup=ReplyKeyboardRemove())
                # User_data contains write_hw_stage, date, day_name, strdate, lesson
                # So just change current stage to 4 (3 is when hw already exists)
                user_data['write_hw_stage'] = 4
                user_data['state'] = 'Добавить'
                return DialogCodes.CODE_WRT_HW
            except IncorrectLessonError:
                update.message.reply_text(f'Урока {lesson} нет в вашем расписании на завтра',
                                          reply_markup=Globals.markup_main)
            except Exception as e:
                LOGGER.error('TODO')
                update.message.reply_text('Неизвестная ошибка при попытке отправки ДЗ!')

            # Any exceptions and other - back to main menu
            return DialogCodes.CODE_MAIN

        # Third call, text is "Удалить / Добавить / Перезаписать / Отмена"
        elif user_data.get('write_hw_stage') == 3:
            # Back to menu without changes
            if text == 'Отмена':
                update.message.reply_text('Возращаемся в главное меню', reply_markup=Globals.markup_main)
                user_data.clear()
                return DialogCodes.CODE_MAIN
            # Delete this homework
            elif text == 'Удалить':
                date = user_data.pop('date', None)
                class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
                lesson = user_data.pop('lesson', None)

                # If some strange thing happened
                if date is None or lesson is None:
                    update.message.reply_text('Кажется, ты забыл указать дату или урок, по которому хочешь удалить дз\n'
                                              'Возвращайся в главное меню', reply_markup=Globals.markup_main)
                    return DialogCodes.CODE_MAIN

                # Trying to delete hw
                try:
                    Globals.DH.hw_delete(class_id, date, lesson)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text('TODO', reply_markup=Globals.markup_main)
                    return DialogCodes.CODE_MAIN

                # If successfully, returns to main menu
                update.message.reply_text('Запись удалена', reply_markup=Globals.markup_main)
                return DialogCodes.CODE_MAIN
            # Add
            elif text == 'Дополнить':
                date = user_data.get('date', None)
                class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
                lesson = user_data.get('lesson', None)

                # If some strange thing happened
                if date is None or lesson is None:
                    update.message.reply_text(
                        'Кажется, ты забыл указать дату или урок, по которому хочешь дополнить дз\n'
                        'Возвращайся в главное меню', reply_markup=Globals.markup_main)
                    return DialogCodes.CODE_MAIN

                # If user has already gave as hw or pic
                hw, pics = user_data.get('hw'), user_data.get('pics')
                if hw is None or pics is None:
                    pass
                else:
                    user_data['write_hw_stage'] = 4
                    user_data['state'] = 'Дополнить'
                    return TelegramBot.write_hw(bot, update, user_data)

                # Asking for hw
                update.message.reply_text('Дополним существующую запись твоей\n'
                                          'Пиши дз', reply_markup=ReplyKeyboardRemove())

                # Setting 4 value to stage
                user_data['write_hw_stage'] = 4
                user_data['state'] = 'Дополнить'
                return DialogCodes.CODE_WRT_HW
            # Rewrite
            elif text == 'Перезаписать':
                date = user_data.get('date', None)
                class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
                lesson = user_data.get('lesson', None)

                # If some strange thing happened
                if date is None or lesson is None:
                    update.message.reply_text(
                        'Кажется, ты забыл указать дату или урок, по которому хочешь дополнить дз\n'
                        'Возвращайся в главное меню', reply_markup=Globals.markup_main)
                    return DialogCodes.CODE_MAIN

                # If user has already gave as hw or pic
                hw, pics = user_data.get('hw'), user_data.get('pics')
                if hw is None or pics is None:
                    pass
                else:
                    user_data['write_hw_stage'] = 4
                    user_data['state'] = 'Перезаписать'
                    return TelegramBot.write_hw(bot, update, user_data)

                # Asking for hw
                update.message.reply_text('Перезапишем имеющуюся запись\n'
                                          'Пиши дз', reply_markup=ReplyKeyboardRemove())

                # Setting 4 value to stage
                user_data['write_hw_stage'] = 4
                user_data['state'] = 'Перезаписать'
                return DialogCodes.CODE_WRT_HW

        # Fourth call, text is homework or photo with caption
        elif user_data.get('write_hw_stage') == 4:
            # Getting values from user_data
            class_id = USERS_DATA[str(update.effective_user['id'])]['class_id']
            state = user_data.get('state')
            date = user_data.get('date')
            strdate = user_data.get('strdate')
            lesson = user_data.get('lesson')
            prev_hw, prev_pics = user_data.get('hw'), user_data.get('pics')

            # If some strange thing happened
            if state is None or date is None or lesson is None:
                LOGGER.error('TODO')
                update.message.reply_text('TODO')
                return DialogCodes.CODE_MAIN

            # If user has already gave hw or pics
            if prev_hw is None or prev_pics is None:
                # If not
                # Checking if user has sent any pics
                photos = update.message.photo
                if len(photos) != 0:
                    photo_id = photos[1].file_id
                    pics = [photo_id]
                    if not (update.message.caption is None) and update.message.caption != '':
                        text += '\nК фото: ' + update.message.caption
                else:
                    pics = []
            else:
                text = prev_hw
                pics = prev_pics

            # Empty hw in this lesson
            if state == 'Добавить':
                try:
                    func_res = Funcs.get_hw_data(bot, update, user_data, 'write_hw_stage 1', lesson)
                    if func_res is None:
                        return DialogCodes.CODE_MAIN
                    else:
                        date, day_name, strdate, lesson, hw_text, pics = func_res

                    # Here if someone have added hw while
                    # Trying to send it
                    try:
                        Funcs.bot_send_homework(bot, update, hw_text, pics)
                    except Exception as e:
                        LOGGER.error('TODO')
                        update.message.reply_text('Упс, не удалось отправить уже сущесвующее ДЗ! '
                                                  'Оно было перезаписано на ваше',
                                                  reply_markup=Globals.markup_main)
                        Globals.DH.hw_edit(class_id, date, lesson, text, pics, hw_replace=True, pics_replace=True)
                        return DialogCodes.CODE_MAIN

                    update.message.reply_text('Что сделать с уже существующей записью?',
                                              reply_markup=Globals.markup_hw_edit)

                    # Asking for action - Delete / Rewrite / Add to current / Cancel
                    user_data['write_hw_stage'] = 3
                    user_data['hw'] = text
                    user_data['pics'] = pics
                    # ---
                except HomeworkNotFoundError:
                    # No homework, good, write it
                    # Trying to write hw
                    try:
                        Globals.DH.hw_write(class_id, date, lesson, text, pics)
                    except Exception as e:
                        LOGGER.error('TODO')
                        update.message.reply_text('TODO')
                        return DialogCodes.CODE_MAIN

                    # Hw was written successfully
                    update.message.reply_text(f'Домашнее задание на {strdate} урок {lesson} успешно добавлено',
                                              reply_markup=Globals.markup_main)
                except IncorrectLessonError:
                    update.message.reply_text(f'Урока {lesson} нет в вашем расписании на завтра',
                                              reply_markup=Globals.markup_main)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text('Неизвестная ошибка при попытке записи ДЗ!')

                return DialogCodes.CODE_MAIN
            # Added new
            elif state == 'Дополнить':
                try:
                    Globals.DH.hw_edit(class_id, date, lesson, text, pics)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text('TODO')
                    return DialogCodes.CODE_MAIN

                # Hw added successfully
                update.message.reply_text(f'На {strdate} урок {lesson} дз успешно дополнено',
                                          reply_markup=Globals.markup_main)
                return DialogCodes.CODE_MAIN
                # ---
            # Rewrite
            elif state == 'Перезаписать':
                try:
                    Globals.DH.hw_edit(class_id, date, lesson, text, pics, hw_replace=True, pics_replace=True)
                except Exception as e:
                    LOGGER.error('TODO')
                    update.message.reply_text('TODO')
                    return DialogCodes.CODE_MAIN

                # Hw added successfully
                update.message.reply_text(f'На {strdate} урок {lesson} дз успешно перезаписано',
                                          reply_markup=Globals.markup_main)
                return DialogCodes.CODE_MAIN
                # ---
            # Error
            else:
                LOGGER.error('TODO')
                update.message.reply_text('TODO', reply_markup=Globals.markup_main)

    @staticmethod
    def help(bot, update: Update, user_data):
        LOGGER.info(f'USER [{str(update.effective_user["id"])}] /help')
        update.message.reply_text('Помощь по боту\n===============\n'
                                  '/help - помощь\n'
                                  '/start - запусить бота\n'
                                  '/cancel - отмена текущих действий\n'
                                  '===============', reply_markup=Globals.markup_main)
        return DialogCodes.CODE_MAIN

    @staticmethod
    def cancel(bot, update: Update, user_data):
        LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "/cancel"')
        update.message.reply_text('Все отменено!', reply_markup=Globals.markup_main)
        user_data.clear()
        return DialogCodes.CODE_MAIN

    @staticmethod
    def error(bot, update: Update, tg_error):
        if update is None:
            LOGGER.info(f'ERROR (no update)')
        else:
            print(tg_error)
            LOGGER.info(f'USER [{str(update.effective_user["id"])}] -- "error"')
            update.message.reply_text('Ой, произошла непредвиденная ошибка. '
                                      'Разработчики уже работают над ее исправлением (нет)',
                                      reply_markup=Globals.markup_main)
        return DialogCodes.CODE_MAIN


if __name__ == '__main__':
    print('Bot script started!')
    load_userdata()
    tgbot = TelegramBot()
