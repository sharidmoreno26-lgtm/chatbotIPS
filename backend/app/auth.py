import datetime as dt

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_HORAS, JWT_SECRET
from .db import get_conn

_bearer = HTTPBearer(auto_error=False)


def hashear_password(plano: str) -> str:
    return bcrypt.hashpw(plano.encode(), bcrypt.gensalt()).decode()


def verificar_password(plano: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(plano.encode(), hash_.encode())
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    vence = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=JWT_HORAS)
    return jwt.encode({"sub": str(usuario_id), "rol": rol, "exp": vence}, JWT_SECRET, algorithm="HS256")


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    conn=Depends(get_conn),
):
    if credenciales is None:
        raise HTTPException(401, "No autenticado")
    try:
        datos = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=["HS256"])
        usuario_id = int(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(401, "Sesión inválida o vencida")
    fila = conn.execute(
        """SELECT u.id, u.nombre, u.usuario, u.estado, r.nombre AS rol
           FROM usuarios u JOIN roles r ON r.id = u.rol_id WHERE u.id = %s""",
        (usuario_id,),
    ).fetchone()
    if fila is None or fila["estado"] != "ACTIVO":
        raise HTTPException(401, "Sesión inválida o vencida")
    return fila


def requiere_roles(*roles: str):
    def dependencia(usuario=Depends(usuario_actual)):
        if usuario["rol"] not in roles:
            raise HTTPException(403, "Tu rol no tiene acceso a este recurso")
        return usuario

    return dependencia
