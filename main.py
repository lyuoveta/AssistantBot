import asyncio
import logging
import random
import traceback
from asyncio import sleep
from functools import wraps

from AiogramStorages.storages import SQLiteStorage
from aiogram import Bot, Dispatcher, types
from openai.types.beta.threads import Run

import db
from openai_settings import openai_connection_pool
from service import get_or_create_thread, monitoring_notify, save_thread, check_access
from settings import TELEGRAM_TOKEN, SQLLITE_DB_PATH
from utils import ExpiringDict

# Включаем логирование, чтобы не пропустить важные сообщения
# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)
s_handler = logging.StreamHandler()
s_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(s_handler)
f_handler = logging.FileHandler('data/run.log')
f_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(f_handler)

# ---- Все для Телеграмма ----
# Объект бота
bot = Bot(
    token=TELEGRAM_TOKEN
)
storage = SQLiteStorage(db_path=SQLLITE_DB_PATH)
# Диспетчер
dp = Dispatcher(
    bot,
    storage=storage
)


# ---------------------------


# Хэндлер на команду /start
@dp.message_handler(commands=['start'])
async def cmd_start(
        message: types.Message
        ):
    await message.answer("")


async def retrieve_run(
        run_id,
        openai_token,
        thread_id
        ):
    async with openai_connection_pool.client(openai_token) as client:
        run_id = client.beta.threads.runs.retrieve(
            run_id=run_id,
            thread_id=thread_id
        )
        return run_id


THREADS_IN_PROGRESS = ExpiringDict(30)


async def create_run(
        thread_id,
        openai_token,
        assistant_id
        ):
    async with openai_connection_pool.client(openai_token) as client:
        return client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )


async def run_and_answer(
        tg_message,
        thread_id,
        openai_token,
        assistant_id,
        _RETRY=1
        ):
    async def process_error(
            error
            ):
        await monitoring_notify(f'ERROR: Run {run.id} finished with {run.status} {error}')
        if _RETRY:
            await sleep(random.randint(20, 40))
            await run_and_answer(tg_message, thread_id, openai_token, assistant_id, _RETRY=_RETRY - 1)
        else:
            (db.ThreadDatabaseModel.delete().where(
                (db.ThreadDatabaseModel.telegram_chat_id == tg_message.chat.id)
            )).execute()
            await tg_message.answer('Кажется что-то пошло не так, попробуйте повторить позже')
        return

    run: Run = await create_run(thread_id, openai_token, assistant_id)
    THREADS_IN_PROGRESS.set(thread_id, run.id)
    try:
        while run.status not in ["cancelled",
                                 "failed",
                                 "completed",
                                 "expired"]:
            logger.info("Running", extra={'status': run.status})
            THREADS_IN_PROGRESS.set(thread_id, run.id)
            run = await retrieve_run(run_id=run.id, openai_token=openai_token, thread_id=thread_id)
    except Exception as e:
        error = traceback.format_exception(e)
        await process_error(error)
        return
    if run.status != 'completed':
        error = f'[{run.last_error.code}:{run.last_error.message}]' if run.last_error else ""
        await process_error(error)
        return
    async with openai_connection_pool.client(openai_token) as client:
        messages = list(client.beta.threads.messages.list(thread_id=thread_id))
    save_thread(thread_id, messages)
    result = []
    messages_it = iter(messages)
    for message in messages_it:
        if message.role == 'user':
            if message.metadata.get('tg_message_id') == str(tg_message.message_id):
                break
        else:
            result.append(message.content[0].text.value)
    if result:
        await tg_message.answer("\n".join(reversed(result[:2])))


@dp.message_handler()
async def handle_message(
        tg_message: types.Message
        ):
    logger.info('Processing Message')
    chat_id = tg_message.chat.id
    text = tg_message.text
    error = check_access(chat_id, text)
    if error:
        await tg_message.answer(error)
        return
    thread_id, openai_token, assistant_id = await get_or_create_thread(chat_id)
    async with openai_connection_pool.client(openai_token) as client:
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=text,
            metadata={'tg_message_id': tg_message.message_id}
        )
    active_run = THREADS_IN_PROGRESS.get(thread_id)
    if active_run:
        await sleep(120)
        if THREADS_IN_PROGRESS.get(thread_id):
            return
        run = await retrieve_run(run_id=active_run, openai_token=openai_token, thread_id=thread_id)
        if run.status == 'completed' or THREADS_IN_PROGRESS.get(thread_id):
            return
    await run_and_answer(tg_message, thread_id, openai_token, assistant_id)


# Запуск процесса поллинга новых апдейтов

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    db.init()
    task = asyncio.run(main())
