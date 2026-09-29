from fastapi import APIRouter, Depends, HTTPException

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ADMIN, FARMACIA, TODOS

router = APIRouter(prefix="/medicamentos", tags=["medicamentos"])


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.listar_medicamentos(conn)


@router.get("/bajo-stock")
def bajo_stock(conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN, FARMACIA))):
    return consultas.medicamentos_bajo_stock(conn)


@router.get("/proximos-vencer")
def proximos_vencer(conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return consultas.medicamentos_proximos_a_vencer(conn)


def _o_404(conn, med_id):
    med = consultas.obtener_medicamento(conn, med_id)
    if med is None:
        raise HTTPException(404, "Medicamento no encontrado")
    return med


@router.get("/{med_id}")
def detalle(med_id: int, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return _o_404(conn, med_id)


@router.get("/{med_id}/inventario")
def inventario(med_id: int, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    med = _o_404(conn, med_id)
    return {
        "medicamento_id": med["id"],
        "nombre": med["nombre"],
        "cantidad_actual": med["cantidad_actual"],
        "stock_minimo": med["stock_minimo"],
        "ubicacion": med["ubicacion"],
        "bajo_minimo": med["cantidad_actual"] < med["stock_minimo"],
    }
