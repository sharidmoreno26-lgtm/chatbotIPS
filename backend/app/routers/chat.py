from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from ..auth import requiere_roles
from ..chatbot.servicio import responder
from ..db import get_conn
from ..roles import TODOS

router = APIRouter(tags=["chat"])


class ChatEntrada(BaseModel):
    mensaje: str = Field(min_length=1, max_length=500)

    @field_validator("mensaje")
    @classmethod
    def no_vacio(cls, valor):
        valor = valor.strip()
        if not valor:
            raise ValueError("El mensaje no puede estar vacío")
        return valor


@router.post("/chat")
def chat(datos: ChatEntrada, conn=Depends(get_conn), usuario=Depends(requiere_roles(*TODOS))):
    return {"respuesta": responder(conn, usuario, datos.mensaje)}
