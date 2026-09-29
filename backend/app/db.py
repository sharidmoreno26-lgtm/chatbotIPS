import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL


def get_conn():
    """Una conexión por petición; se cierra sola al terminar."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn
