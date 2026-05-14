from sqlalchemy.orm import Session, joinedload
import models


def obtener_productos(db: Session):
    return db.query(models.Producto).all()


def obtener_pedidos_recientes(db: Session):
    return db.query(models.Pedido).order_by(models.Pedido.fecha_hora.desc()).limit(10).all()


def sumar_stock_producto(db: Session, producto_id: int, cantidad: int):
    producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if producto:
        producto.stock_actual += cantidad
        if producto.stock_actual > producto.stock_minimo:
            producto.alerta_roja = False
        nuevo_suministro = models.EntradaSuministro(
            producto_id=producto_id,
            cantidad_ingresada=cantidad
        )
        db.add(nuevo_suministro)
        db.commit()
        db.refresh(producto)
    return producto


def actualizar_estado_pedido(db: Session, pedido_id: int, nuevo_estado: str):
    ESTADOS_VALIDOS = {"recibido", "en ruta", "en camino", "entregado", "cancelado"}
    if nuevo_estado not in ESTADOS_VALIDOS:
        raise ValueError(f"Estado invalido: {nuevo_estado}")
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if pedido:
        pedido.estado_logistico = nuevo_estado
        db.commit()
        db.refresh(pedido)
    return pedido


def crear_producto(db: Session, nombre: str, marca: str, precio_venta: float,
                   costo_compra: float, stock_actual: int, stock_minimo: int):
    nuevo = models.Producto(
        nombre=nombre, marca=marca, precio_venta=precio_venta,
        costo_compra=costo_compra, stock_actual=stock_actual,
        stock_minimo=stock_minimo, alerta_roja=stock_actual <= stock_minimo,
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


def eliminar_producto(db: Session, producto_id: int):
    producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
    if not producto:
        return False
    tiene_pedidos = db.query(models.DetallePedido).filter(
        models.DetallePedido.producto_id == producto_id
    ).first()
    if tiene_pedidos:
        producto.nombre = f"[DESCONTINUADO] {producto.nombre}"
        producto.stock_actual = 0
        producto.stock_minimo = 0
        db.commit()
        return "descontinuado"
    db.delete(producto)
    db.commit()
    return True


# ── EDICIÓN DE PEDIDOS ────────────────────────────────────────

def obtener_pedido_con_items(db: Session, pedido_id: int):
    """Carga un pedido completo con sus items y productos."""
    return (
        db.query(models.Pedido)
        .options(
            joinedload(models.Pedido.cliente),
            joinedload(models.Pedido.items).joinedload(models.DetallePedido.producto),
        )
        .filter(models.Pedido.id == pedido_id)
        .first()
    )


def recalcular_total_pedido(db: Session, pedido_id: int):
    """Suma todos los subtotales de los items y actualiza total_pedido."""
    pedido = db.query(models.Pedido).filter(models.Pedido.id == pedido_id).first()
    if not pedido:
        return None
    items = db.query(models.DetallePedido).filter(
        models.DetallePedido.pedido_id == pedido_id
    ).all()
    total = 0.0
    for item in items:
        prod = db.query(models.Producto).filter(models.Producto.id == item.producto_id).first()
        if prod:
            total += (prod.precio_venta or 0) * (item.cantidad or 0)
    pedido.total_pedido = total
    db.commit()
    db.refresh(pedido)
    return pedido


def actualizar_cantidad_item(db: Session, detalle_id: int, nueva_cantidad: int):
    """Cambia la cantidad de un item existente. Si cantidad <= 0 lo elimina."""
    item = db.query(models.DetallePedido).filter(models.DetallePedido.id == detalle_id).first()
    if not item:
        return None
    pedido_id = item.pedido_id
    if nueva_cantidad <= 0:
        db.delete(item)
    else:
        item.cantidad = nueva_cantidad
    db.commit()
    recalcular_total_pedido(db, pedido_id)
    return pedido_id


def agregar_item_pedido(db: Session, pedido_id: int, producto_id: int, cantidad: int):
    """Agrega un producto al pedido. Si ya existe suma la cantidad."""
    item_existente = db.query(models.DetallePedido).filter(
        models.DetallePedido.pedido_id == pedido_id,
        models.DetallePedido.producto_id == producto_id,
    ).first()
    if item_existente:
        item_existente.cantidad += cantidad
    else:
        nuevo_item = models.DetallePedido(
            pedido_id=pedido_id,
            producto_id=producto_id,
            cantidad=cantidad,
        )
        db.add(nuevo_item)
    db.commit()
    recalcular_total_pedido(db, pedido_id)
    return pedido_id


def eliminar_item_pedido(db: Session, detalle_id: int):
    """Elimina un item del pedido y recalcula el total."""
    item = db.query(models.DetallePedido).filter(models.DetallePedido.id == detalle_id).first()
    if not item:
        return None
    pedido_id = item.pedido_id
    db.delete(item)
    db.commit()
    recalcular_total_pedido(db, pedido_id)
    return pedido_id