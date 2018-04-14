import json, datetime, time, calendar, logging
from EduExceptions import *

lessons = ['Английский язык', 'Астрономия', 'Биология', 'География',
           'Геометрия', 'Информатика', 'История', 'Литература',
           'Алгебра', 'ОБЖ', 'Обществознание', 'Русский язык',
           'Физика', 'Физкультура', 'Химия',
           'Электив рус. яз', 'Электив алгебра', 'Электив литра']

class_by_id = {'10_1': '10А Физмат', '10_2': '10Б Соцгум', '10_3': '10В Биохим'}


with open('data/timetables.json', encoding='utf-8') as file:
    timetable = dict(json.load(file))

with open('data/keys.json', encoding='utf-8') as file:
    classes_keys = dict(json.load(file))


day_translate = {'Monday': 'Понедельник',
                 'Tuesday': 'Вторник',
                 'Wednesday': 'Среда',
                 'Thursday': 'Четверг',
                 'Friday': 'Пятница',
                 'Saturday': 'Суббота'}


class DataHandler:
    def __init__(self):
        # self.logger = logging.basicConfig(filename="DataHandler.log", level=logging.INFO)
        self.db_load()

    def check_correct_data(self, class_id: str, date: datetime.date, lesson: str):
        # if int(class_id) not in StringsAdditional.schools:
        #     self.logger.error('No such school with id %s' % class_id)
        #     raise IncorrectSchoolError()
        if lesson not in lessons:
            raise IncorrectLessonError()

    def hw_exists(self, class_id: str, date: datetime.date, lesson: str):
        self.check_correct_data(class_id, date, lesson)
        strdate = self.__date_to_str__(date)
        if strdate not in self.db[class_id]:
            return False
        if lesson not in self.db[class_id][strdate]:
            return False
        if self.db[class_id][strdate][lesson]['text'] != '' or self.db[class_id][strdate][lesson]['pics'] != list():
            return True
        return False

    def hw_get(self, class_id: str, date: datetime.date, lesson: str) -> dict():
        self.check_correct_data(class_id, date, lesson)
        if not self.hw_exists(class_id, date, lesson):
            raise HomeworkNotFoundError()

        strdate = self.__date_to_str__(date)
        return self.db[class_id][strdate][lesson]

    def hw_write(self, class_id: str, date: datetime.date, lesson: str, hw: str = '', pics: list = list()):
        self.check_correct_data(class_id, date, lesson)

        strdate = self.__date_to_str__(date)
        if strdate not in self.db[class_id]:
            self.__gen_new_date__(class_id, strdate)

        if self.hw_exists(class_id, date, lesson):
            raise HomeworkExistsError()

        hw = hw.replace("'", '"').replace('"', '%^%')

        self.db[class_id][strdate][lesson]['text'] = hw
        self.db[class_id][strdate][lesson]['pics'] = pics

        self.db_save()

    def hw_edit(self, class_id: str, date: datetime.date, lesson: str, hw: str = '', pics: list = list(),
                hw_replace = False, pics_replace = False):
        self.check_correct_data(class_id, date, lesson)

        strdate = self.__date_to_str__(date)
        if strdate not in self.db[class_id]:
            self.hw_write(class_id, date, lesson, hw, pics)

        if hw != '':
            hw = hw.replace("'", '"').replace('"', '%^%')

            if hw_replace:
                self.db[class_id][strdate][lesson]['text'] = hw
            else:
                self.db[class_id][strdate][lesson]['text'] += '\n' + hw

        if pics_replace:
            self.db[class_id][strdate][lesson]['pics'].clear()

        if len(pics) != 0:
            if pics_replace:
                self.db[class_id][strdate][lesson]['pics'] = pics
            else:
                self.db[class_id][strdate][lesson]['pics'] += pics

        self.db_save()

    def hw_delete(self, class_id: str, date: datetime.date, lesson: str):
        self.check_correct_data(class_id, date, lesson)
        strdate = self.__date_to_str__(date)

        if self.hw_exists(class_id, date, lesson):
            self.db[class_id][strdate][lesson] = {'text': '', 'pics': list()}

        self.db_save()

    def db_load(self):
        with open('db.json', encoding='utf-8') as file:
            self.db = dict(json.load(file))
            for class_id in self.db:
                for date in self.db[class_id]:
                    for subject in self.db[class_id][date]:
                        text, pics = self.db[class_id][date][subject]['text'], self.db[class_id][date][subject]['pics']
                        self.db[class_id][date][subject] = {'text': text.replace('%^%', '"'), 'pics': pics}
        print('DB loaded!')

    def db_save(self):
        with open('db.json', 'w', encoding='utf-8') as file:
            db_to_save = self.db.copy()
            for class_id in self.db:
                for date in self.db[class_id]:
                    for subject in self.db[class_id][date]:
                        text, pics = self.db[class_id][date][subject]['text'], self.db[class_id][date][subject]['pics']
                        db_to_save[class_id][date][subject] = {'text': text.replace('"', '%^%'), 'pics': pics}
            file.write(str(db_to_save).replace("'", '"'))
        print('DB saved!')

    def get_lessons(self, class_id: str, date: datetime.date) -> list:
        day = time.strftime('%A', time.localtime(calendar.timegm(date.timetuple())))
        if day == 'Sunday':
            raise ValueError
        return timetable[class_id][day]

    def __gen_new_date__(self, class_id, strdate: str):
        date = self.__str_to_date__(strdate)
        day = time.strftime('%A', time.localtime(calendar.timegm(date.timetuple())))
        if day not in timetable[class_id] and day != 'Sunday':
            # self.logger.error('Day %s not in timetable!' % day)
            return
        lessons_dict = {}
        for lesson in timetable[class_id][day]:
            lessons_dict[lesson] = {'text': '', 'pics': list()}
        self.db[class_id][strdate] = lessons_dict

    def __str_to_date__(self, strdate: str) -> datetime.date:
        date = datetime.date(*map(int, reversed(strdate.split('.'))))
        return date

    def __date_to_str__(self, date: datetime.date) -> str:
        strdate = date.strftime('%d.%m.%Y')
        return strdate
