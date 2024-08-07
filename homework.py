import json
import logging
import os
import time
from datetime import datetime
from http import HTTPStatus

from dotenv import load_dotenv
from requests import exceptions as req_excpt
import requests
from telebot import TeleBot

load_dotenv()


logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
START_PRACTICUM = 1549962000
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class AbsentEnvironmentVariable(Exception):
    """Класс исключения для переменных окружения."""

    def __init__(self, *args):
        """Инициализация."""
        self.arg = args[0] if args else None

    def __str__(self):
        """Текст ислючения."""
        return ('Отсутствует обязательная переменная окружения: '
                f'\'{self.arg}\' '
                'Программа принудительно остановлена.')


class ResponseNot200(Exception):
    """Ответ сервера не равен 200."""


def check_tokens():
    """Проверяет доступность переменных окружения."""
    try:
        if not TELEGRAM_TOKEN:
            raise AbsentEnvironmentVariable('TELEGRAM_TOKEN')
        if not TELEGRAM_CHAT_ID:
            raise AbsentEnvironmentVariable('TELEGRAM_CHAT_ID')
        if not PRACTICUM_TOKEN:
            raise AbsentEnvironmentVariable('PRACTICUM_TOKEN')
    except AbsentEnvironmentVariable as error:
        logger.critical(error)
        quit()


def send_message(bot, message):
    """Отправка сообщений в Telegram."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение отправлено: {message}')
    except Exception as error:
        logger.error(f'Cбой при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Получение данных из YaPracticum."""
    try:
        headers = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
        payload = {'from_date': timestamp}
        response = requests.get(ENDPOINT, headers=headers, params=payload)
        if response.status_code != 200:
            logger.error(f'Сбой в работе программы: Эндпоинт {ENDPOINT}, '
                         f'HTTPStatus: {response.status_code}')
            raise ResponseNot200
    except requests.RequestException as error:
        logger.error(f'Сбой в работе программы {error}')
    return response.json()


def check_response(response):
    """Проверяет ответ API."""
    if 'homeworks' not in response:
        logger.error('Сбой: в response отсутствует homeworks')
        raise TypeError
    if not isinstance(response, dict):
        logger.error('Сбой: response не dict')
        raise TypeError
    if not isinstance(response['homeworks'], list):
        logger.error('Сбой: response[\'homeworks\'] не list')
        raise TypeError
    homework = response.get('homeworks')
    return homework[0]


def parse_status(homework):
    """Извлекает информацию из homeworks."""
    if 'status' not in homework:
        logger.error('Сбой: в homework отсутствует status')
        raise TypeError
    if 'homework_name' not in homework:
        logger.error('Сбой: в homework отсутствует homework_name')
        raise TypeError
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        logger.error('Сбой: неизвестный статус')
        raise TypeError
    if status == '':
        logger.error('Сбой: пустой статус')
        raise TypeError
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    now = datetime.now()
    send_message(bot, f'Бот запущен! {now.strftime("%d.%m.%Y %H:%M")}')
    tmp_status = 'reviewing'
    errors = True
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            print(homework)
            if homework and tmp_status != homework.get('status'):
                message = parse_status(homework)
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
