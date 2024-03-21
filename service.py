import datetime
import logging
import os

from db import ThreadDatabaseModel, WhiteListItemModel, InviteCodeModel
from openai_settings import openai_connection_pool, OPENAI_TOKENS_ASSISTANT_ID
from settings import NOTIFICATION_CHAT_ID, THREADS_PATH

logger = logging.getLogger()


async def monitoring_notify(message):
    from main import bot
    await bot.send_message(NOTIFICATION_CHAT_ID, message)


async def get_or_create_thread(chat_id):
    """
    Получает или создает новую ветвь (Thread) по идентификатору чата.

    Args:
        chat_id: Идентификатор чата.

    Returns:
        thread_id: Идентификатор созданной или найденной ветви.
    """
    db_thread: ThreadDatabaseModel = (ThreadDatabaseModel.select().where(
        (ThreadDatabaseModel.telegram_chat_id == chat_id) &
        (ThreadDatabaseModel.updated_at >= datetime.date.today())
    )).first()
    if db_thread and (db_thread.openai_token, db_thread.assistant_id) in OPENAI_TOKENS_ASSISTANT_ID.items():
        logger.info('GET THREAD', extra=dict(chat_id=chat_id, thread_id=db_thread.id))
        return db_thread.id, db_thread.openai_token, db_thread.assistant_id
    else:
        if db_thread:
            db_thread.delete()
        openai_token = openai_connection_pool.get_token()
        assistant_id = openai_connection_pool.get_assistant_id(openai_token)
        async with openai_connection_pool.client(openai_token) as client:
            openai_thread = client.beta.threads.create()
        thread_id = openai_thread.id
        ThreadDatabaseModel.create(
            id=thread_id,
            telegram_chat_id=chat_id,
            openai_token=openai_token,
            assistant_id=assistant_id
        )
        return thread_id, openai_token, assistant_id


def save_thread(thread_id, messages: list):
    try:
        with open(os.path.join(THREADS_PATH, f'{thread_id}.txt'), 'w', encoding='utf-8') as f:
            for message in reversed(messages):
                f.write(
                    f'[{datetime.datetime.fromtimestamp(message.created_at).isoformat()}][{message.role}]: {repr(message.content[0].text.value)}\n')
    except Exception as e:
        logger.exception(e)


def check_access(chat_id, text):
    exists: bool = (WhiteListItemModel.select().where(
        (WhiteListItemModel.telegram_chat_id == chat_id) &
        (WhiteListItemModel.expires_at >= datetime.datetime.now().timestamp())
    )).exists()
    if exists:
        return None
    invite_code: InviteCodeModel = (InviteCodeModel.select().where(
        (InviteCodeModel.code == text) &
        (InviteCodeModel.expires_at >= datetime.datetime.now().timestamp())
    )).first()
    if invite_code:
        WhiteListItemModel.create(
            expires_at=invite_code.expires_at,
            telegram_chat_id=chat_id
        )
        return "Приятно познакомиться!"

    return "Введите, пожалуйста, пригласительный код, мне не разрешают общаться с незнакомцами"
