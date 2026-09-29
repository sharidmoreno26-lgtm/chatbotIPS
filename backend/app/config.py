import os

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_HORAS = int(os.getenv("JWT_HORAS", "8"))
