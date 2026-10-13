"""
Configuracion del modulo Productos (Entidades > Generales > Productos >
Producto). Mapeo verificado contra un export real del 2026-10-13 (83
productos habilitados, 35 anunciantes, `Id` unico, sin duplicados de
Anunciante + Nombre).

Se carga por reemplazo total (no upsert): si un producto se deshabilita o
se borra en Advertys tiene que desaparecer tambien de la tabla, porque
esta tabla alimenta el combo Producto del alta de OT en `ot/`.
"""

# "Nombre en el Excel de Advertys" -> "nombre_interno". La columna "N°"
# (numero) se ignora a proposito: es igual a `Id` y su byte cambia entre
# modulos ("N°" vs "Nº", ver CLAUDE.md), no vale el riesgo de un KeyError.
COLUMN_MAP = {
    "Id": "id_advertys",
    "Nombre Producto": "nombre",
    "Anunciante": "anunciante",
    "Categoria": "categoria",
    "Marca": "marca",
}

REQUIRED_COLUMNS = ["id_advertys", "nombre", "anunciante"]
UNIQUE_KEY_COLUMN = "id_advertys"

DB_TABLE = "productos"
