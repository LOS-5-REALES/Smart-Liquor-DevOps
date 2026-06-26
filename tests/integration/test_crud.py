import pytest

import crud
import models


def _crear_producto(db, **overrides):
    datos = dict(
        nombre="Ron Cartavio",
        marca="Cartavio",
        precio_venta=35.0,
        costo_compra=20.0,
        stock_actual=10,
        stock_minimo=5,
    )
    datos.update(overrides)
    return crud.crear_producto(db, **datos)


class TestCrearProducto:
    def test_no_activa_alerta_si_stock_supera_minimo(self, db):
        producto = _crear_producto(db, stock_actual=10, stock_minimo=5)
        assert producto.alerta_roja is False

    def test_activa_alerta_si_stock_es_menor_o_igual_al_minimo(self, db):
        producto = _crear_producto(db, stock_actual=3, stock_minimo=5)
        assert producto.alerta_roja is True

    def test_producto_queda_persistido(self, db):
        _crear_producto(db)
        assert len(crud.obtener_productos(db)) == 1


class TestSumarStockProducto:
    def test_incrementa_stock_y_registra_suministro(self, db):
        producto = _crear_producto(db, stock_actual=2, stock_minimo=5)

        actualizado = crud.sumar_stock_producto(db, producto.id, 10)

        assert actualizado.stock_actual == 12
        suministros = db.query(models.EntradaSuministro).filter(
            models.EntradaSuministro.producto_id == producto.id
        ).all()
        assert len(suministros) == 1
        assert suministros[0].cantidad_ingresada == 10

    def test_desactiva_alerta_roja_al_superar_minimo(self, db):
        producto = _crear_producto(db, stock_actual=1, stock_minimo=5)
        assert producto.alerta_roja is True

        actualizado = crud.sumar_stock_producto(db, producto.id, 20)

        assert actualizado.alerta_roja is False

    def test_producto_inexistente_devuelve_none(self, db):
        assert crud.sumar_stock_producto(db, 9999, 5) is None


class TestActualizarEstadoPedido:
    def _crear_pedido(self, db):
        pedido = models.Pedido(estado_logistico="recibido")
        db.add(pedido)
        db.commit()
        db.refresh(pedido)
        return pedido

    def test_actualiza_a_estado_valido(self, db):
        pedido = self._crear_pedido(db)
        actualizado = crud.actualizar_estado_pedido(db, pedido.id, "en camino")
        assert actualizado.estado_logistico == "en camino"

    def test_estado_invalido_lanza_value_error(self, db):
        pedido = self._crear_pedido(db)
        with pytest.raises(ValueError):
            crud.actualizar_estado_pedido(db, pedido.id, "estado_inventado")

    def test_pedido_inexistente_devuelve_none(self, db):
        assert crud.actualizar_estado_pedido(db, 9999, "entregado") is None


class TestEliminarProducto:
    def test_elimina_fisicamente_si_no_tiene_pedidos(self, db):
        producto = _crear_producto(db)

        resultado = crud.eliminar_producto(db, producto.id)

        assert resultado is True
        assert crud.obtener_productos(db) == []

    def test_descontinua_si_tiene_pedidos_asociados(self, db):
        producto = _crear_producto(db)
        pedido = models.Pedido()
        db.add(pedido)
        db.commit()
        db.add(models.DetallePedido(pedido_id=pedido.id, producto_id=producto.id, cantidad=2))
        db.commit()

        resultado = crud.eliminar_producto(db, producto.id)

        db.refresh(producto)
        assert resultado == "descontinuado"
        assert producto.nombre.startswith("[DESCONTINUADO]")
        assert producto.stock_actual == 0
        assert producto.stock_minimo == 0

    def test_producto_inexistente_devuelve_false(self, db):
        assert crud.eliminar_producto(db, 9999) is False


class TestRecalcularTotalPedido:
    def test_suma_precio_por_cantidad_de_cada_item(self, db):
        producto_a = _crear_producto(db, nombre="A", precio_venta=10.0)
        producto_b = _crear_producto(db, nombre="B", precio_venta=5.0)
        pedido = models.Pedido()
        db.add(pedido)
        db.commit()
        db.add(models.DetallePedido(pedido_id=pedido.id, producto_id=producto_a.id, cantidad=2))
        db.add(models.DetallePedido(pedido_id=pedido.id, producto_id=producto_b.id, cantidad=3))
        db.commit()

        actualizado = crud.recalcular_total_pedido(db, pedido.id)

        assert actualizado.total_pedido == 35.0

    def test_pedido_inexistente_devuelve_none(self, db):
        assert crud.recalcular_total_pedido(db, 9999) is None


class TestActualizarCantidadItem:
    def _crear_pedido_con_item(self, db, cantidad=2, precio=10.0):
        producto = _crear_producto(db, precio_venta=precio)
        pedido = models.Pedido()
        db.add(pedido)
        db.commit()
        item = models.DetallePedido(pedido_id=pedido.id, producto_id=producto.id, cantidad=cantidad)
        db.add(item)
        db.commit()
        db.refresh(item)
        return pedido, item

    def test_actualiza_cantidad_y_recalcula_total(self, db):
        pedido, item = self._crear_pedido_con_item(db, cantidad=2, precio=10.0)

        crud.actualizar_cantidad_item(db, item.id, 5)

        db.refresh(pedido)
        assert pedido.total_pedido == 50.0

    def test_cantidad_cero_elimina_el_item(self, db):
        pedido, item = self._crear_pedido_con_item(db, cantidad=2, precio=10.0)

        crud.actualizar_cantidad_item(db, item.id, 0)

        assert db.query(models.DetallePedido).filter(models.DetallePedido.id == item.id).first() is None

    def test_item_inexistente_devuelve_none(self, db):
        assert crud.actualizar_cantidad_item(db, 9999, 5) is None
