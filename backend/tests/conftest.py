import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]
INIT_SQL = Path(os.getenv("INIT_SQL", "/db/init.sql"))


@pytest.fixture(autouse=True)
def bd_limpia():
    """Restaura la BD con los datos ficticios antes de cada prueba."""
    with psycopg.connect(DATABASE_URL, autocommit=True) as c:
        c.execute(INIT_SQL.read_text(encoding="utf-8"))


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as c:
        yield c


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app)


def _cabecera(client, usuario):
    r = client.post("/auth/login", json={"usuario": usuario, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def admin(client):
    return _cabecera(client, "admin")


@pytest.fixture
def farmacia(client):
    return _cabecera(client, "farmacia")


@pytest.fixture
def almacen(client):
    return _cabecera(client, "almacen")


@pytest.fixture
def fecha_mes(conn):
    """Devuelve 'DD/MM/YYYY' del día `dia` (0 = primer día) del mes actual."""

    def _fecha(dia):
        fila = conn.execute(
            "SELECT to_char(date_trunc('month', CURRENT_DATE)::date + %s::int, 'DD/MM/YYYY') AS f",
            (dia,),
        ).fetchone()
        return fila["f"]

    return _fecha
