from datetime import datetime
from types import SimpleNamespace

from utils import parsear_fecha, filtrar_pedidos_por_fecha


def _pedido(fecha_hora):
    return SimpleNamespace(fecha_hora=fecha_hora)


class TestParsearFecha:
    def test_formato_valido(self):
        assert parsear_fecha("21/05/2026") == datetime(2026, 5, 21)

    def test_string_vacio_devuelve_none(self):
        assert parsear_fecha("") is None

    def test_solo_espacios_devuelve_none(self):
        assert parsear_fecha("   ") is None

    def test_formato_invalido_devuelve_none(self):
        assert parsear_fecha("2026-05-21") is None

    def test_fecha_no_existente_devuelve_none(self):
        assert parsear_fecha("31/02/2026") is None


class TestFiltrarPedidosPorFecha:
    def test_sin_fechas_devuelve_todos(self):
        pedidos = [_pedido(datetime(2026, 1, 1)), _pedido(datetime(2026, 6, 1))]
        assert filtrar_pedidos_por_fecha(pedidos, "", "") == pedidos

    def test_rango_completo(self):
        dentro = _pedido(datetime(2026, 5, 10))
        antes = _pedido(datetime(2026, 1, 1))
        despues = _pedido(datetime(2026, 12, 1))
        pedidos = [antes, dentro, despues]

        resultado = filtrar_pedidos_por_fecha(pedidos, "01/05/2026", "31/05/2026")

        assert resultado == [dentro]

    def test_solo_fecha_desde(self):
        viejo = _pedido(datetime(2026, 1, 1))
        nuevo = _pedido(datetime(2026, 6, 1))

        resultado = filtrar_pedidos_por_fecha([viejo, nuevo], "01/03/2026", "")

        assert resultado == [nuevo]

    def test_solo_fecha_hasta(self):
        viejo = _pedido(datetime(2026, 1, 1))
        nuevo = _pedido(datetime(2026, 6, 1))

        resultado = filtrar_pedidos_por_fecha([viejo, nuevo], "", "01/03/2026")

        assert resultado == [viejo]

    def test_ignora_pedidos_sin_fecha_hora(self):
        sin_fecha = _pedido(None)
        con_fecha = _pedido(datetime(2026, 5, 10))

        resultado = filtrar_pedidos_por_fecha([sin_fecha, con_fecha], "01/05/2026", "31/05/2026")

        assert resultado == [con_fecha]

    def test_limite_inclusivo_en_ambos_extremos(self):
        limite_inferior = _pedido(datetime(2026, 5, 1))
        limite_superior = _pedido(datetime(2026, 5, 31))

        resultado = filtrar_pedidos_por_fecha(
            [limite_inferior, limite_superior], "01/05/2026", "31/05/2026"
        )

        assert resultado == [limite_inferior, limite_superior]
