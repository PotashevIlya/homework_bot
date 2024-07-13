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


load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
GLOBAL_VARS_NAMES = ('PRACTICUM_TOKEN', 'TELEGRAM_CHAT_ID', 'TELEGRAM_TOKEN')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

GLOBAL_TOKENS_ERROR = 'Отсутсвуют все необходимые переменные окружения.'
DETAIL_TOKEN_ERROR = 'Отсутствует обязательная переменная окружения {var}.'
SEND_MESSAGE_SUCCESS = 'Бот отправил сообщение: {message}'
SEND_MESSAGE_ERROR = 'Ошибка при отправке сообщения: {message}. Ошибка: {err}'
CONNECTION_ERROR = ('Ошибка API. Параметры: {url}, {headers}, {params}.'
                    'Ошибка: {err}')
SERVER_FAILURE_ERROR = ('Отказ сервера. Параметры: {url}, {headers}, {params}.'
                        'Ключ: {key} Ошибка: {err}.')
NOT_OK_STATUS_CODE = ('Код ответа сервера не OK.'
                      'Параметры: {url}, {headers}, {params}. Код: {code}')
DATA_TYPE_ERROR = 'Некорретный тип данных в ответе API: {type}'
NO_HOMEWORK_KEY_ERROR = 'Отсутвует ключ "homeworks" в словаре.'
KEY_DATA_TYPE_ERROR = 'Некорректный тип данных под ключем "homeworks": {type}'
HOMEWORK_NAME_ERROR = 'Отсутствует информация о названии домашки.'
HOMEWORK_STATUS_ERROR = 'Отсутствует информация о статусе домашки.'
UNEXPECTED_HOMEWORK_STATUS = 'Некорретный статус домашки: {status}'
STATUS_CHANGE_MESSAGE = 'Изменился статус проверки работы "{name}". {status}'
NO_NEW_STATUS = 'Домашка ещё не взята на проверку.'
STATUS_CHANGED = 'Статус работы изменился.'
ERROR_MESSAGE = 'Сбой в работе программы: {error}'


def check_tokens():
    """Проверяем наличие обязательных переменных окружения."""
    flag = False
    for var in GLOBAL_VARS_NAMES:
        if globals()[var] is None:
            logger.critical(DETAIL_TOKEN_ERROR.format(var=var))
            flag = True
    if flag:
        raise ValueError(GLOBAL_TOKENS_ERROR)


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE_SUCCESS.format(message=message))
        return True
    except Exception as err:
        logger.exception(SEND_MESSAGE_ERROR.format(message=message, err=err))
    return False


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    request_params = dict(
        url=ENDPOINT,
        headers=HEADERS,
        params={'from_date': timestamp}
    )
    try:
        response = requests.get(**request_params)
    except requests.RequestException as err:
        raise ConnectionError(
            CONNECTION_ERROR.format(**request_params, err=err)
        )
    json_response = response.json()
    for key in ('code', 'error'):
        if key in json_response:
            raise ServerAnswerException(
                SERVER_FAILURE_ERROR.format(
                    **request_params,
                    key=key,
                    err=json_response[key])
            )
    if response.status_code != HTTPStatus.OK:
        raise ServerAnswerException(
            NOT_OK_STATUS_CODE.format(
                **request_params,
                code=response.status_code)
        )
    return json_response


def check_response(response):
    """Проверяем данные в ответе API."""
    if not isinstance(response, dict):
        raise TypeError(DATA_TYPE_ERROR.format(type=type(response)))
    if 'homeworks' not in response:
        raise KeyError(NO_HOMEWORK_KEY_ERROR)
    homeworks_data = response['homeworks']
    if not isinstance(homeworks_data, list):
        raise TypeError(KEY_DATA_TYPE_ERROR.format(type=type(homeworks_data)))


def parse_status(homework):
    """Проверяем статус работы."""
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_ERROR)
    if 'status' not in homework:
        raise KeyError(HOMEWORK_STATUS_ERROR)
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(UNEXPECTED_HOMEWORK_STATUS.format(status=status))
    return STATUS_CHANGE_MESSAGE.format(
        name=homework['homework_name'],
        status=HOMEWORK_VERDICTS.get(status)
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_verdict = None
    last_error = None
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if len(response['homeworks']) == 0:
                logger.debug(NO_NEW_STATUS)
                continue
            current_verdict = parse_status(response['homeworks'][0])
            if current_verdict != last_verdict and send_message(
                    bot, current_verdict):
                last_verdict = current_verdict
                timestamp = response.get('current_date', timestamp)
                logger.debug(STATUS_CHANGED)
            last_error = None
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logger.error(message)
            if message != last_error and send_message(bot, message):
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
