from fastapi import APIRouter, Depends

from ..auth import requiere_roles
from ..db import get_conn
from ..roles import TODOS

router = APIRouter(prefix="/servicios", tags=["servicios"])


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return conn.execute("SELECT id, nombre FROM servicios ORDER BY id").fetchall()
