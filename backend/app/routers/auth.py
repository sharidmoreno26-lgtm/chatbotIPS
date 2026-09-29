from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import crear_token, usuario_actual, verificar_password
from ..db import get_conn

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=72)


def _resumen(fila):
    return {"nombre": fila["nombre"], "usuario": fila["usuario"], "rol": fila["rol"]}


@router.post("/login")
def login(datos: LoginEntrada, conn=Depends(get_conn)):
    fila = conn.execute(
        """SELECT u.id, u.nombre, u.usuario, u.password_hash, u.estado, r.nombre AS rol
           FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.usuario = %s""",
        (datos.usuario,),
    ).fetchone()
    if (
        fila is None
        or fila["estado"] != "ACTIVO"
        or not verificar_password(datos.password, fila["password_hash"])
    ):
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    return {"token": crear_token(fila["id"], fila["rol"]), "usuario": _resumen(fila)}


@router.get("/me")
def me(usuario=Depends(usuario_actual)):
    return _resumen(usuario)
