# app/utils.py
from datetime import datetime

def parsear_fecha(texto: str) -> datetime | None:
    """
    Convierte una cadena de texto en un objeto datetime.

    Args:
        texto (str): Fecha en formato "DD/MM/AAAA".

    Returns:
        datetime | None: El objeto datetime si el formato es correcto,
        o None si la cadena está vacía o el formato es inválido.
    """
    texto = texto.strip()
    if not texto:
        return None
    try:
        # Corregido a %Y mayúscula para años de 4 dígitos
        return datetime.strptime(texto, "%d/%m/%Y")
    except ValueError:
        return None

def filtrar_pedidos_por_fecha(pedidos: list, fecha_inicio_str: str, fecha_fin_str: str) -> list:
    """
    Filtra una lista de pedidos descartando aquellos que estén fuera del rango de fechas.

    La función normaliza las fechas de los pedidos ignorando las horas y minutos
    para realizar una comparación estricta por día (00:00:00).

    Args:
        pedidos (list): Lista de objetos `models.Pedido`.
        fecha_inicio_str (str): Fecha de inicio en formato "DD/MM/AAAA". Puede ser un string vacío.
        fecha_fin_str (str): Fecha de fin en formato "DD/MM/AAAA". Puede ser un string vacío.

    Returns:
        list: Nueva lista que contiene únicamente los pedidos que cumplen el criterio de fecha.
    """
    desde = parsear_fecha(fecha_inicio_str)
    hasta = parsear_fecha(fecha_fin_str)

    if not desde and not hasta:
        return pedidos

    resultado = []
    for p in pedidos:
        if not p.fecha_hora:
            continue

        fh = p.fecha_hora if isinstance(p.fecha_hora, datetime) else datetime.fromisoformat(str(p.fecha_hora))
        fh_solo = fh.replace(hour=0, minute=0, second=0, microsecond=0)

        if desde and hasta and desde <= fh_solo <= hasta:
            resultado.append(p)
        elif desde and not hasta and fh_solo >= desde:
            resultado.append(p)
        elif hasta and not desde and fh_solo <= hasta:
            resultado.append(p)

    return resultado