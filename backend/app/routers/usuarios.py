from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth import hashear_password, requiere_roles
from ..db import get_conn
from ..roles import ADMIN

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    usuario: str = Field(pattern=r"^[a-z0-9_]{3,30}$")
    password: str = Field(min_length=8, max_length=72)
    rol: Literal["ADMINISTRADOR", "FARMACIA", "ALMACENISTA"]

    @field_validator("password")
    @classmethod
    def maximo_72_bytes(cls, valor):
        if len(valor.encode()) > 72:
            raise ValueError("La contraseña es demasiado larga")
        return valor


@router.get("")
def listar(conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN))):
    return conn.execute(
        """SELECT u.id, u.nombre, u.usuario, r.nombre AS rol, u.estado
           FROM usuarios u JOIN roles r ON r.id = u.rol_id ORDER BY u.id"""
    ).fetchall()


@router.post("", status_code=201)
def crear(datos: UsuarioNuevo, conn=Depends(get_conn), usuario=Depends(requiere_roles(ADMIN))):
    if conn.execute("SELECT 1 FROM usuarios WHERE usuario = %s", (datos.usuario,)).fetchone():
        raise HTTPException(409, "Ese nombre de usuario ya existe")
    fila = conn.execute(
        """INSERT INTO usuarios (nombre, usuario, password_hash, rol_id)
           VALUES (%s, %s, %s, (SELECT id FROM roles WHERE nombre = %s)) RETURNING id""",
        (datos.nombre, datos.usuario, hashear_password(datos.password), datos.rol),
    ).fetchone()
    conn.commit()
    return {"id": fila["id"]}
