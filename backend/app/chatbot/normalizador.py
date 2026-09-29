import re
import unicodedata


def normalizar(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    solo_letras = re.sub(r"[^a-z0-9\s]", " ", sin_tildes.lower())
    return re.sub(r"\s+", " ", solo_letras).strip()
