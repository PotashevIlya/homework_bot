import logging
import os
import requests
import time

from http import HTTPStatus

from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяем наличие обязательных переменных окружения."""
    if PRACTICUM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN'
        )
        raise Exception(
            'Отсутствует обязательная переменная окружения: PRACTICUM_TOKEN'
        )
    elif TELEGRAM_TOKEN is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN'
        )
        raise Exception(
            'Отсутствует обязательная переменная окружения: TELEGRAM_TOKEN'
        )
    elif TELEGRAM_CHAT_ID is None:
        logger.critical(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID'
        )
        raise Exception(
            'Отсутствует обязательная переменная окружения: TELEGRAM_CHAT_ID'
        )


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот отправил сообщение: {message}')
    except Exception:
        logger.error(f'Ошибка при отправке сообщения: {message}')


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
        )
        if response.status_code != HTTPStatus.OK:
            message = f'Ошибка {response.status_code}: {response.reason}'
            logger.error(message)
            raise Exception(message)
        return response.json()
    except requests.RequestException as error:
        logger.error(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверяем данные в ответе API."""
    if type(response) is not dict:
        logger.error(f'Некорректный тип данных в ответе API: {type(response)}')
        raise TypeError(
            f'Некорректный тип данных в ответе API: {type(response)}')
    elif type(response.get('homeworks')) is not list:
        logger.error(
            f'Некорректный тип данных под ключем "homeworks":'
            f'{type(response.get("homeworks"))}')
        raise TypeError(
            f'Некорректный тип данных под ключем "homeworks":'
            f'{type(response.get("homeworks"))}')
    elif len(response.get('homeworks')) == 0:
        logger.debug('Последняя работа ещё не взята на проверку.')
        return
    return response.get('homeworks')[0]


def parse_status(homework):
    """Проверяем статус работы."""
    if 'homework_name' not in homework:
        logger.error('Отсутсвует информация о названии домашки.')
        raise Exception('Отсутсвует информация о названии домашки.')
    elif 'status' not in homework:
        logger.error('Отсутствует информация о статусе домашки.')
        raise Exception('Отсутствует информация о статусе домашки.')
    elif homework.get('status') not in HOMEWORK_VERDICTS.keys():
        logger.error('Некорректный статус домашки.')
        raise Exception('Некорректный статус домашки.')
    homework_name = homework.get('homework_name')
    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = None
    last_error = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                current_status = parse_status(homework)
                if current_status != last_status:
                    send_message(bot, current_status)
                    last_status = current_status
                    logger.debug('Статус работы изменился.')
            last_error = None
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != last_error:
                send_message(bot, message)
                last_error = message
        finally:
            time.sleep(RETRY_PERIOD)
            continue


if __name__ == '__main__':
    main()
