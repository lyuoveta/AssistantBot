import logging
import os.path

import httpx
from openai import OpenAI

from settings import PROXIES_SETTINGS

TOKENS = [
    # "sk-",

]

TEMPLATE = dict(
    MODEL='gpt-3.5-turbo-1106',
    INSTRUCTIONS="""\
1. Понимание Запроса:
- Проанализируйте запрос, чтобы определить ключевые моменты, такие как симптомы, имя БАДа, вопрос о совместимости или побочных эффектах.
- Отнесите запрос к соответствующей категории: "Pharmacology", "Action serving", "For whom", "Remark", "For special groups", "Compatibility", "Side effects".

2. Ответ на Вопросы:
- Найдите информацию в файле knowledge_base.json, соответствующую категории и ключевым моментам запроса.
- Предложите пользователю краткую, но полную информацию на основе данных из базы знаний.
- Если информация относится к категории "Remark" или "For special groups", выделите её как цитату.

3. Взаимодействие с Пользователем и Сбор Информации:
- Если запрос связан с побочными эффектами ("Side effects"), использовать knowledge_base_mean.json для предоставления данных о частоте и серьёзности эффектов.
- Если требуется информация о "Compatibility", задайте вопрос о других принимаемых препаратах и оцените возможные взаимодействия.
- Для категории "For whom" выясните, относится ли пользователь к какой-либо особой группе (например, беременные, пожилые люди) для более точной рекомендации.

4. Рекомендации по Симптомам:
- Спросите у пользователя о симптомах и принимаемых препаратах для индивидуального подбора БАДов.
- Предложите БАДы, соответствующие описанным симптомам и с учетом уже принимаемых препаратов и принадлежности к специальным группам.

5. Обзор Данных:
- При запросе суммарных данных по параметру (такому как популярность или эффективность), представьте обзорный ответ, основанный на агрегированной информации из JSON базы знаний.
""",
    TOOLS=[
        {"type": 'retrieval'},
    ],
    FILES=[
        'files/knowledge base.json',
        'files/knowledge base mean.json',
    ]
)

FILES_TO_UPLOAD = TEMPLATE['FILES']
with open('tokens_assistants.json', 'a') as res:
    for token in TOKENS:
        try:
            client: OpenAI = OpenAI(
                api_key=token,
                http_client=httpx.Client(proxies=PROXIES_SETTINGS)
            )

            files = []
            for file in FILES_TO_UPLOAD:
                with open(file, 'rb') as f:
                    file_obj = client.files.create(
                        file=f,
                        purpose='assistants'
                    )
                files.append(file_obj)
            assistant = client.beta.assistants.create(
                model=TEMPLATE['MODEL'],
                instructions=TEMPLATE['INSTRUCTIONS'],
                file_ids=[file.id for file in files],
                tools=TEMPLATE['TOOLS']
            )
            res.write(f"\n\"{token}\":\"{assistant.id}\",")
        except Exception as e:
            logging.warning(token)
            logging.exception(e)
