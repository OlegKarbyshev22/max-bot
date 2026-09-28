import psycopg
from psycopg.rows import dict_row

from agent.settings import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_USER,
    require_database_password,
)


def get_db_connection():
    return psycopg.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=require_database_password(),
        row_factory=dict_row,
        connect_timeout=10,
    )
