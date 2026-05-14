from sqlalchemy.orm import Session
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
    ESTADOS_VALIDOS = {"recibido", "en ruta", "entregado", "cancelado"}
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