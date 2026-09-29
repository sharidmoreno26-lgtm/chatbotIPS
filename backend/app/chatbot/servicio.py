import re

from .. import consultas
from .intenciones import detectar_intencion
from .normalizador import normalizar
from .permisos import PERMISOS
from .respuestas import MANEJADORES

NO_ENTENDIDO = (
    "No pude identificar tu consulta. Puedes preguntarme sobre inventario, "
    "medicamentos, movimientos, vencimientos o ubicaciones."
)
SIN_PERMISO = "Esa consulta no está disponible para tu rol."


def buscar_medicamento(conn, texto):
    """Busca el nombre (o principio activo) de un medicamento dentro del texto normalizado."""
    candidatos = sorted(consultas.listar_medicamentos(conn), key=lambda m: -len(m["nombre"]))
    for med in candidatos:
        for nombre in (med["nombre"], med["principio_activo"]):
            if re.search(rf"\b{re.escape(normalizar(nombre))}\b", texto):
                return med
    return None


def responder(conn, usuario, mensaje):
    texto = normalizar(mensaje)
    med = buscar_medicamento(conn, texto)
    intencion = detectar_intencion(texto, med is not None)
    if intencion is None:
        return NO_ENTENDIDO
    if usuario["rol"] not in PERMISOS[intencion]:
        return SIN_PERMISO
    return MANEJADORES[intencion](conn, med)
