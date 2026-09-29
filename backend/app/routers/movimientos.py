from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ALMACEN, FARMACIA, TODOS

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


class MovimientoNuevo(BaseModel):
    medicamento_id: int = Field(gt=0)
    tipo: Literal["SALIDA"]
    cantidad: int = Field(gt=0, le=100000)


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn)


@router.get("/entradas")
def entradas(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn, "ENTRADA")


@router.get("/salidas")
def salidas(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_movimientos(conn, "SALIDA")


@router.post("", status_code=201)
def registrar(
    datos: MovimientoNuevo,
    conn=Depends(get_conn),
    usuario=Depends(requiere_roles(FARMACIA, ALMACEN)),
):
    try:
        resultado = consultas.registrar_movimiento(
            conn, datos.medicamento_id, datos.tipo, datos.cantidad, usuario["id"]
        )
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))
    conn.commit()
    return resultado
