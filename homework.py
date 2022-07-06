import os
from sys import stdout
import logging
import requests
import telegram
import time
from dotenv import load_dotenv
from exceptions import (VariableDoesNotExist,
                        StatusCodeError,
                        ServerAnswerError,
                        AnswerError,
                        )

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stdout)
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
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info(f'Бот отправил сообщение: {message}')
    except Exception:
        logger.error('Cбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    """Запрос к API Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    logger.debug(f'Сервер вернул ответ: {response}')
    if response.status_code == 200:
        return response.json()
    else:
        logger.error(
            f'Сбой в работе программы: эндпойнт {ENDPOINT} недоступен'
        )
        raise StatusCodeError(
            f'Сбой в работе программы: эндпойнт {ENDPOINT} недоступен'
        )


def check_response(response):
    """Проверка ответа API."""
    try:
        if isinstance(response, dict):
            homeworks = response['homeworks']
            logger.debug(f'Ключ homeworks: {homeworks}')
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
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    return False


def main():
    """Основная логика работы бота."""
    if check_tokens():
        pass
    else:
        logger.critical('Отсутствуют обязательные переменные окружения')
        raise VariableDoesNotExist('Нет обязательных переменных окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if len(homeworks) > 0:
                message = parse_status(homeworks[0])
                if message is not None:
                    send_message(bot, message)
            else:
                logger.debug('В ответе отсутствуют новые статусы')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
