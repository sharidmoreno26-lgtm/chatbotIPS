from app.chatbot.normalizador import normalizar


def test_quita_tildes_signos_y_mayusculas():
    assert normalizar("¿Cuántas UNIDADES de Acetaminofén hay?!") == "cuantas unidades de acetaminofen hay"


def test_colapsa_espacios_y_maneja_enie_y_simbolos():
    assert normalizar("  año   '; DROP-- %s 😀 ") == "ano drop s"


def test_texto_vacio():
    assert normalizar("   ") == ""
