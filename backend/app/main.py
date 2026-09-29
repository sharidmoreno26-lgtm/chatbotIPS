from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .routers import auth, chat, ingresos, medicamentos, movimientos, servicios, usuarios

app = FastAPI(title="Chatbot IPS", root_path="/api")


@app.exception_handler(RequestValidationError)
async def error_de_validacion(request, exc):
    """422 sin devolver el dato recibido (un surrogate suelto haría fallar la respuesta con 500)."""
    errores = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errores})


app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(medicamentos.router)
app.include_router(movimientos.router)
app.include_router(ingresos.router)
app.include_router(servicios.router)
app.include_router(chat.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}
