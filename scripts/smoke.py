"""Prueba de humo: recorre las 15 preguntas del proyecto a través de nginx → FastAPI → PostgreSQL."""
import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"

PREGUNTAS = {
    "admin": [
        "¿Cuántos medicamentos tenemos registrados actualmente?",
        "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
        "¿Qué medicamentos están próximos a vencer durante los próximos 30 días?",
        "¿Cuántas entradas y salidas de medicamentos se registraron durante este mes?",
        "¿Qué medicamento tiene mayor movimiento durante este mes?",
    ],
    "farmacia": [
        "¿Cuántas unidades hay disponibles de acetaminofén?",
        "¿Cuáles son los medicamentos que están por debajo del mínimo establecido?",
        "¿Qué medicamentos están próximos a vencer?",
        "¿Cuántas unidades de acetaminofén ingresaron durante este mes?",
        "¿Cuántas unidades de acetaminofén salieron durante este mes?",
    ],
    "almacen": [
        "¿Dónde está ubicada la insulina?",
        "¿Cuántas unidades hay disponibles de insulina?",
        "¿Cuándo fue registrada la última entrada de acetaminofén?",
        "¿Cuándo fue registrada la última salida de acetaminofén?",
        "¿Qué medicamentos debo revisar por vencimiento?",
    ],
}
RECHAZOS = ("No pude identificar tu consulta", "Esa consulta no está disponible")


def post(ruta, cuerpo, token=None):
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(
        f"{BASE}/api{ruta}", data=json.dumps(cuerpo).encode(), headers=cabeceras, method="POST"
    )
    with urllib.request.urlopen(peticion) as respuesta:
        return json.load(respuesta)


fallos = 0
for usuario, preguntas in PREGUNTAS.items():
    token = post("/auth/login", {"usuario": usuario, "password": "demo1234"})["token"]
    print(f"\n=== {usuario} ===")
    for pregunta in preguntas:
        respuesta = post("/chat", {"mensaje": pregunta}, token)["respuesta"]
        valida = not respuesta.startswith(RECHAZOS)
        fallos += not valida
        print(f"{'OK  ' if valida else 'FAIL'} {pregunta}\n     → {respuesta}\n")

print("Resultado:", "TODO BIEN" if fallos == 0 else f"{fallos} preguntas fallaron")
sys.exit(1 if fallos else 0)
