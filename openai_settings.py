import asyncio
import logging
import random
from collections import defaultdict
from contextlib import asynccontextmanager
from functools import partial
from typing import Dict

import httpx
from openai import OpenAI

from settings import PROXIES_SETTINGS

ASSISTANT_ID = #'asst_'

OPENAI_TOKENS_ASSISTANT_ID = {
    # 'sk-': 'asst_',

}

logging.getLogger()


def round_token():
    tokens = [*OPENAI_TOKENS_ASSISTANT_ID.keys()]
    random.shuffle(tokens)
    while True:
        for token in tokens:
            yield token


token_iter = round_token()


class OpenAIClientPool:
    def __init__(self, delay):
        self._tokens_lock: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._tasks = set()
        self._delay = delay

    def release_after_timeout(self, task, openai_token):
        self._tasks.discard(task)
        self._tokens_lock[openai_token].release()

    @asynccontextmanager
    async def client(self, openai_token):
        await self._tokens_lock[openai_token].acquire()
        try:
            yield OpenAI(
                api_key=openai_token,
                http_client=httpx.Client(proxies=PROXIES_SETTINGS)
            )
        finally:
            task = asyncio.create_task(asyncio.sleep(self._delay))
            self._tasks.add(task)
            task.add_done_callback(partial(self.release_after_timeout, openai_token=openai_token))

    def get_token(self):
        return next(token_iter)

    def get_assistant_id(self, openai_token):
        return OPENAI_TOKENS_ASSISTANT_ID[openai_token]


openai_connection_pool = OpenAIClientPool(delay=10)
