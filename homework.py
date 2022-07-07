import os
import sys
import logging
import requests
import telegram
import time
from dotenv import load_dotenv
from exceptions import (SendMessageError,
                        StatusCodeError,
                        ServerAnswerError,
                        AnswerError,
                        )
from http import HTTPStatus

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения в Telegram."""
    try:
        logger.debug(f'Отправка сообщения: {message}')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info(f'Бот отправил сообщение: {message}')
    except Exception as error:
        raise SendMessageError(
            f'Cбой при отправке сообщения в Telegram: {error}'
        )


def get_api_answer(current_timestamp):
    """Запрос к API Практикума."""
    timestamp = current_timestamp or int(time.time())
    logger.debug(f'Запрос с timestamp: {timestamp}')
    params = {'from_date': timestamp}
    payload = {'url': ENDPOINT, 'headers': HEADERS, 'params': params}
    response = requests.get(**payload)
    logger.debug(f'Сервер вернул ответ: {response}')
    if response.status_code == HTTPStatus.OK:
        return response.json()
    else:
        raise StatusCodeError(
            f'Сбой в работе программы: эндпойнт {ENDPOINT} недоступен.'
            f'В запросе переданы аргументы: {payload}.'
            f'Ответ сервера: {response.content}.'
        )


def check_response(response):
    """Проверка ответа API."""
    try:
        if isinstance(response, dict):
            homeworks = response['homeworks']
            logger.debug(f'Ключ homeworks: {response}')
            if not isinstance(homeworks, list):
                raise AnswerError
            return homeworks
        else:
            raise TypeError
    except AnswerError:
        raise AnswerError('Домашняя работа не в виде списка')
    except TypeError:
        raise TypeError('В функцию не передан словарь')
    except Exception:
        raise ServerAnswerError('Нет нужного кода ответа от сервера')


def parse_status(homework):
    """Получение статуса домашней работы."""
    try:
        homework_name = homework.get('homework_name')
        if homework_name is None:
            raise KeyError
        homework_status = homework.get('status')
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except KeyError:
        raise KeyError('Нет имени домашней работы')
    except Exception:
        raise ServerAnswerError('Нет задокументированного ответа от сервера')


def check_tokens():
    """Проверка наличия токенов."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message is not None:
                    send_message(bot, message)
            else:
                logger.debug('В ответе отсутствуют новые статусы')
            current_timestamp = response['current_date']
        except Exception as error:
            logger.error(f'Сбой при работе программы: {error}')
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
