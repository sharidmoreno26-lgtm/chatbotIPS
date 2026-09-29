from fastapi import FastAPI

from .routers import auth, medicamentos, movimientos, servicios, usuarios

app = FastAPI(title="Chatbot IPS", root_path="/api")

app.include_router(auth.router)
app.include_router(usuarios.router)
app.include_router(medicamentos.router)
app.include_router(movimientos.router)
app.include_router(servicios.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}
