"""Программа для проверки статуса домашней работы с помощью бота Telegram."""
from http import HTTPStatus
import logging
import os
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot

load_dotenv()

logger = logging.getLogger(__name__)
handlers = [
    logging.StreamHandler(),
    logging.FileHandler(filename=__file__ + '.log', encoding='utf-8')
]

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

CHECK_TOKENS_ERROR = 'Отсутствует обязательная переменная окружения.'
SEND_MESSAGE_SUCCESS = 'Бот отправил сообщение: {}'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {}'
API_ERROR = 'Ошибка при запросе к API. Параметры: {}, {}, {}'
SERVER_ERROR = 'Отказ сервера. Параметры: {}, {}, {}. Ошибка: {}. Код: {}'
DATA_TYPE_ERROR = 'Некорретный тип данных в ответе API: {}'
NO_HOMEWORK_KEY_ERROR = 'Отсутвует ключ "homeworks" в словаре.'
KEY_DATA_TYPE_ERROR = 'Некорректный тип данных под ключем "homeworks": {}'
HOMEWORK_NAME_ERROR = 'Отсутствует информация о названии домашки.'
HOMEWORK_STATUS_ERROR = 'Отсутствует информация о статусе домашки.'
UNEXPECTED_HOMEWORK_STATUS = 'Некорретный статус домашки: {}'
STATUS_CHANGE_MESSAGE = 'Изменился статус проверки работы "{}". {}'


def check_tokens():
    """Проверяем наличие обязательных переменных окружения."""
    tokens = (PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)
    for token in tokens:
        if token is None:
            logger.critical(CHECK_TOKENS_ERROR)
            raise ValueError(CHECK_TOKENS_ERROR)


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message))
        return True
    except Exception:
        logger.exception(SEND_MESSAGE_ERROR.format(message))


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.RequestException:
        raise ConnectionError(API_ERROR.format(ENDPOINT, HEADERS, params))
    if response.status_code != HTTPStatus.OK:
        if 'code' in response.json().keys():
            raise requests.RequestException(
                SERVER_ERROR.format(
                    ENDPOINT,
                    HEADERS,
                    params,
                    response.json().get('code'),
                    response.status_code
                )
            )
        elif 'error' in response.json().keys():
            raise requests.RequestException(
                SERVER_ERROR.format(
                    ENDPOINT,
                    HEADERS,
                    params,
                    response.json().get('error'),
                    response.status_code
                )
            )
        else:
            raise requests.RequestException(
                SERVER_ERROR.format(
                    ENDPOINT,
                    HEADERS,
                    params,
                    None,
                    response.status_code
                )
            )
    return response.json()


def check_response(response):
    """Проверяем данные в ответе API."""
    if type(response) is not dict:
        raise TypeError(DATA_TYPE_ERROR.format(type(response)))
    if issubclass(type(response), dict) is False:
        raise TypeError(DATA_TYPE_ERROR.format(type(response)))
    if 'homeworks' not in response.keys():
        raise TypeError(NO_HOMEWORK_KEY_ERROR)
    homeworks_data = response.get('homeworks')
    if type(homeworks_data) is not list:
        raise TypeError(KEY_DATA_TYPE_ERROR.format(type(homeworks_data)))
    if issubclass(type(homeworks_data), list) is False:
        raise TypeError(KEY_DATA_TYPE_ERROR.format(type(homeworks_data)))
    if len(homeworks_data) > 0:
        return homeworks_data[0]


def parse_status(homework):
    """Проверяем статус работы."""
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_ERROR)
    if 'status' not in homework:
        raise KeyError(HOMEWORK_STATUS_ERROR)
    if homework.get('status') not in HOMEWORK_VERDICTS.keys():
        raise ValueError(
            UNEXPECTED_HOMEWORK_STATUS.format(homework.get('status'))
        )
    return STATUS_CHANGE_MESSAGE.format(
        homework.get('homework_name'),
        HOMEWORK_VERDICTS.get(homework.get('status'))
    )


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
            timestamp = response.get('current_date')
            homework = check_response(response)
            if not homework:
                logger.debug('Отсутствуют работы с новым статусом.')
                continue
            current_status = parse_status(homework)
            if current_status != last_status:
                if send_message(bot, current_status):
                    last_status = current_status
                    logger.debug('Статус работы изменился.')
            last_error = None
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error:
                if send_message(bot, message):
                    last_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(funcName)s - %(lineno)s - %(asctime)s - %(name)s - '
        '%(levelname)s - %(message)s',
        level=logging.DEBUG,
        handlers=handlers
    )
    main()
