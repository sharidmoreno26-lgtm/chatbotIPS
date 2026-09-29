from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .. import consultas
from ..auth import requiere_roles
from ..db import get_conn
from ..roles import ALMACEN, FARMACIA

router = APIRouter(prefix="/ingresos", tags=["ingresos"])

_SIN_NUL = r"^[^\x00]*$"


class NuevoMedicamento(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    nombre: str = Field(min_length=1, max_length=80, pattern=_SIN_NUL)
    principio_activo: str = Field(min_length=1, max_length=80, pattern=_SIN_NUL)
    presentacion: str = Field(min_length=1, max_length=60, pattern=_SIN_NUL)
    stock_minimo: int = Field(ge=0, le=100000)
    ubicacion: str = Field(min_length=1, max_length=60, pattern=_SIN_NUL)


class IngresoNuevo(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    medicamento_id: int | None = Field(default=None, gt=0)
    nuevo_medicamento: NuevoMedicamento | None = None
    cantidad: int = Field(ge=1, le=100000)
    lote: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._/-]+$")
    fecha_vencimiento: date
    fecha_ingreso: date


@router.post("", status_code=201)
def registrar(
    datos: IngresoNuevo,
    conn=Depends(get_conn),
    usuario=Depends(requiere_roles(FARMACIA, ALMACEN)),
):
    if (datos.medicamento_id is None) == (datos.nuevo_medicamento is None):
        raise HTTPException(422, "Elija un medicamento existente o indique uno nuevo, no ambos ni ninguno")
    if datos.fecha_vencimiento <= datos.fecha_ingreso:
        raise HTTPException(422, "La fecha de vencimiento debe ser posterior a la fecha de ingreso")
    hoy = conn.execute("SELECT CURRENT_DATE AS hoy").fetchone()["hoy"]
    if datos.fecha_ingreso > hoy:
        raise HTTPException(422, "La fecha de ingreso no puede ser futura")
    if datos.fecha_vencimiento < hoy:
        raise HTTPException(422, "El lote ya está vencido")
    nuevo = datos.nuevo_medicamento.model_dump() if datos.nuevo_medicamento else None
    try:
        resultado = consultas.registrar_ingreso(
            conn,
            usuario["id"],
            datos.cantidad,
            datos.lote,
            datos.fecha_vencimiento,
            datos.fecha_ingreso,
            datos.medicamento_id,
            nuevo,
        )
    except LookupError as error:
        raise HTTPException(404, str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))
    conn.commit()
    return resultado
