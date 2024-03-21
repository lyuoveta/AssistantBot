from peewee import Model, AutoField, CharField, IntegerField, SQL, TimestampField, SqliteDatabase, TimeField, \
    DateTimeField
from settings import SQLLITE_DB_PATH

db = SqliteDatabase(SQLLITE_DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class ThreadDatabaseModel(BaseModel):
    id = CharField(primary_key=True)
    openai_token = CharField()
    assistant_id = CharField()
    telegram_chat_id = IntegerField(index=True)
    updated_at = DateTimeField(constraints=[SQL("DEFAULT CURRENT_TIMESTAMP")], null=True)

    class Meta:
        database = db
        table_name = 'threads'


class InviteCodeModel(BaseModel):
    code = CharField(primary_key=True)
    expires_at = DateTimeField()

    class Meta:
        database = db
        table_name = 'invite_codes'


class WhiteListItemModel(BaseModel):
    expires_at = DateTimeField()
    telegram_chat_id = IntegerField(index=True)

    class Meta:
        database = db
        table_name = 'white_list'


def init():
    db.create_tables([
        ThreadDatabaseModel,
        InviteCodeModel,
        WhiteListItemModel,
    ])
