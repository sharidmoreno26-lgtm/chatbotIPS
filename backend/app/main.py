from fastapi import FastAPI

from .routers import auth, usuarios

app = FastAPI(title="Chatbot IPS", root_path="/api")

app.include_router(auth.router)
app.include_router(usuarios.router)


@app.get("/salud", tags=["sistema"])
def salud():
    return {"estado": "ok"}
