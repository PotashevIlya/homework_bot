"""Программа для проверки статуса домашней работы с помощью бота Telegram."""
from http import HTTPStatus
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
from telebot import TeleBot


class ServerAnswerException(Exception):
    """Исключение на случай неожиданного ответа сервера."""

    pass


load_dotenv()

logger = logging.getLogger(__name__)

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

GLOBAL_TOKENS_ERROR = 'Отсутсвуют все необходимые переменные окружения.'
DETAIL_TOKEN_ERROR = 'Отсутствует обязательная переменная окружения {}.'
SEND_MESSAGE_SUCCESS = 'Бот отправил сообщение: {}'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {}. Ошибка: {}'
CONNECTION_ERROR = 'Ошибка при запросе к API. Параметры: {}, {}, {}. Ошибка: {}'
SERVER_FAILURE_ERROR = 'Отказ сервера. Параметры: {}, {}, {}. Ошибка: {}.'
HTTP_ERROR = 'Код ответа сервера не OK. параметры: {}, {}, {}. Код: {}'
DATA_TYPE_ERROR = 'Некорретный тип данных в ответе API: {}'
NO_HOMEWORK_KEY_ERROR = 'Отсутвует ключ "homeworks" в словаре.'
KEY_DATA_TYPE_ERROR = 'Некорректный тип данных под ключем "homeworks": {}'
HOMEWORK_NAME_ERROR = 'Отсутствует информация о названии домашки.'
HOMEWORK_STATUS_ERROR = 'Отсутствует информация о статусе домашки.'
UNEXPECTED_HOMEWORK_STATUS = 'Некорретный статус домашки: {}'
STATUS_CHANGE_MESSAGE = 'Изменился статус проверки работы "{}". {}'


def check_tokens():
    """Проверяем наличие обязательных переменных окружения."""
    tokens = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
              'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN
              }
    counter = 0
    for token in tokens:
        if tokens[token] is None:
            logger.critical(DETAIL_TOKEN_ERROR.format(token))
            counter += 1
    if counter > 0:
        raise ValueError(GLOBAL_TOKENS_ERROR)


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message))
        return True
    except Exception as err:
        logger.exception(SEND_MESSAGE_ERROR.format(message, err))
    return False


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.RequestException as err:
        raise ConnectionError(
            CONNECTION_ERROR.format(ENDPOINT, HEADERS, params, err)
        )
    json_response = response.json()
    error_keys = ('code', 'error')
    for key in error_keys:
        if key in json_response.keys():
            raise ServerAnswerException(
                SERVER_FAILURE_ERROR.format(
                    ENDPOINT,
                    HEADERS,
                    params,
                    json_response[key]
                )
            )
    if response.status_code != HTTPStatus.OK:
        raise ServerAnswerException(
            HTTP_ERROR.format(
                ENDPOINT,
                HEADERS,
                params,
                response.status_code))
    return json_response


def check_response(response):
    """Проверяем данные в ответе API."""
    if type(response) is not dict or issubclass(type(response), dict) is False:
        raise TypeError(DATA_TYPE_ERROR.format(type(response)))
    if 'homeworks' not in response.keys():
        raise KeyError(NO_HOMEWORK_KEY_ERROR)
    homeworks_data = response['homeworks']
    if type(homeworks_data) is not list or issubclass(
            type(homeworks_data), list) is False:
        raise TypeError(KEY_DATA_TYPE_ERROR.format(type(homeworks_data)))


def parse_status(homework):
    """Проверяем статус работы."""
    try:
        homework_status = homework['status']
    except KeyError:
        logger.debug('У домашки не обновился статус.')
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_ERROR)
    if 'status' not in homework:
        raise KeyError(HOMEWORK_STATUS_ERROR)
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise ValueError(
            UNEXPECTED_HOMEWORK_STATUS.format(homework.get('status'))
        )
    return STATUS_CHANGE_MESSAGE.format(
        homework.get('homework_name'),
        HOMEWORK_VERDICTS.get(homework_status)
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
            check_response(response)
            current_status = parse_status(response['homeworks'][0])
            if current_status != last_status and send_message(
                    bot, current_status) is True:
                last_status = current_status
                timestamp = response.get('current_date', timestamp)
                logger.debug('Статус работы изменился.')
            last_error = None
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error and send_message(bot, message) is True:
                last_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(funcName)s - %(lineno)s - %(asctime)s - %(name)s - '
        '%(levelname)s - %(message)s',
        level=logging.DEBUG,
        handlers=[
            logging.StreamHandler(stream=sys.stdout),
            logging.FileHandler(filename=__file__ + '.log', encoding='utf-8')
        ]
    )
    main()
