# app/crud.py
"""
Módulo CRUD (Create, Read, Update, Delete).

Contiene toda la lógica de negocio y las transacciones con la base de datos.
Ninguna función en este módulo debe interactuar directamente con la interfaz
de usuario, únicamente reciben datos y devuelven modelos o valores simples.
"""

from sqlalchemy.orm import Session, joinedload
import models
from constants import ESTADOS_VALIDOS


def obtener_productos(db: Session):
    """
    Recupera el catálogo completo de productos disponibles.

    Args:
        db (Session): Sesión activa de la base de datos.

    Returns:
        list[models.Producto]: Una lista con todos los productos registrados.
    """
    return db.query(models.Producto).all()


def obtener_pedidos_recientes(db: Session):
    """
    Obtiene los últimos 10 pedidos registrados en el sistema.

    Args:
        db (Session): Sesión activa de la base de datos.

    Returns:
        list[models.Pedido]: Lista de pedidos ordenados desde el más reciente.
    """
    return db.query(models.Pedido).order_by(models.Pedido.fecha_hora.desc()).limit(10).all()


def sumar_stock_producto(db: Session, producto_id: int, cantidad: int):
    """
    Incrementa el inventario de un producto y registra el movimiento.

    Si el nuevo stock supera el umbral mínimo del producto, desactiva
    automáticamente la alerta roja. Además, deja un registro histórico en la
    tabla de EntradaSuministro.

    Args:
        db (Session): Sesión activa de la base de datos.
        producto_id (int): El ID del producto a reabastecer.
        cantidad (int): Número de unidades que ingresan al almacén.

    Returns:
        models.Producto | None: El objeto del producto modificado,
        o None si el producto no existe.
    """
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
    """
    Modifica la fase logística en la que se encuentra un pedido.

    Args:
        db (Session): Sesión activa de la base de datos.
        pedido_id (int): El ID del pedido a actualizar.
        nuevo_estado (str): La nueva fase del pedido.

    Raises:
        ValueError: Si el estado proporcionado no se encuentra en `ESTADOS_VALIDOS`.

    Returns:
        models.Pedido | None: El pedido actualizado, o None si no existe.
    """
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
    """
    Registra un nuevo producto en el catálogo y evalúa su nivel de stock.

    Al crear el producto, el sistema calcula automáticamente si este debe
    nacer con una `alerta_roja` activada, comparando el stock actual con el mínimo.

    Args:
        db (Session): Sesión activa de la base de datos SQLAlchemy.
        nombre (str): Nombre comercial del producto.
        marca (str): Marca fabricante del producto.
        precio_venta (float): Precio final de venta al cliente (en Soles).
        costo_compra (float): Costo de adquisición al proveedor (en Soles).
        stock_actual (int): Unidades físicas que ingresan inicialmente al almacén.
        stock_minimo (int): Umbral a partir del cual el sistema debe generar alertas.

    Returns:
        models.Producto: El objeto del producto recién insertado en la base de datos.
    """
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
    """
    Elimina un producto o le aplica un "borrado lógico" si tiene historial.

    Para evitar corromper los reportes de ventas pasadas (integridad referencial),
    si el producto ya está vinculado a un pedido, no se elimina de la base de datos.
    En su lugar, se renombra a "[DESCONTINUADO]", y su stock se reduce a cero.

    Args:
        db (Session): Sesión activa de la base de datos.
        producto_id (int): El ID del producto a procesar.

    Returns:
        bool | str:
            - True si el producto fue eliminado físicamente.
            - "descontinuado" si se aplicó borrado lógico.
            - False si el producto no existe.
    """
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
    """
    Recupera la información integral de una orden de compra.

    Utiliza pre-carga (joinedload) para extraer al cliente asociado, los items
    del detalle y los productos correspondientes en una sola consulta SQL,
    evitando problemas de rendimiento (N+1 queries).

    Args:
        db (Session): Sesión activa de la base de datos.
        pedido_id (int): ID del pedido a consultar.

    Returns:
        models.Pedido | None: El objeto pedido completamente poblado, o None.
    """
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
    """
    Calcula dinámicamente el costo total de un pedido iterando sobre sus items.

    Multiplica la cantidad de cada item por el precio de venta actual del producto
    y guarda el resultado en el campo `total_pedido`.

    Args:
        db (Session): Sesión activa de la base de datos.
        pedido_id (int): ID del pedido que será recalculado.

    Returns:
        models.Pedido | None: El pedido con el total actualizado.
    """
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
    """
    Modifica la cantidad solicitada de un producto dentro de un pedido.

    Si la nueva cantidad proporcionada es menor o igual a cero, elimina el item
    del pedido por completo. Al finalizar, dispara el recálculo del total.

    Args:
        db (Session): Sesión activa de la base de datos.
        detalle_id (int): El ID específico de la línea de detalle (`DetallePedido`).
        nueva_cantidad (int): La nueva cantidad deseada.

    Returns:
        int | None: El ID del pedido padre que fue afectado, o None si falló.
    """
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
    """
    Añade un producto al carrito de un pedido existente.

    Si el producto ya se encontraba listado en el pedido, en lugar de crear
    una fila duplicada, simplemente suma la nueva cantidad a la ya existente.
    Al finalizar, dispara el recálculo del total.

    Args:
        db (Session): Sesión activa de la base de datos.
        pedido_id (int): ID del pedido objetivo.
        producto_id (int): ID del producto que se desea agregar.
        cantidad (int): Número de unidades a agregar (debe ser mayor a 0).

    Returns:
        int: El ID del pedido modificado.
    """
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
    """
    Extrae definitivamente un producto de un pedido y ajusta el monto a pagar.

    Args:
        db (Session): Sesión activa de la base de datos.
        detalle_id (int): El ID específico de la línea de detalle a remover.

    Returns:
        int | None: El ID del pedido padre que fue afectado, o None si no existe.
    """
    item = db.query(models.DetallePedido).filter(models.DetallePedido.id == detalle_id).first()
    if not item:
        return None

    pedido_id = item.pedido_id
    db.delete(item)
    db.commit()

    recalcular_total_pedido(db, pedido_id)
    return pedido_id

def buscar_clientes(db: Session, query: str = ""):
    """
    Busca clientes por nombre o telefono con sus pedidos cargados.
    Si query esta vacio retorna todos los clientes.
    """
    q = (
        db.query(models.Cliente)
        .options(joinedload(models.Cliente.pedidos))
        .order_by(models.Cliente.id.desc())
    )
    if query.strip():
        termino = f"%{query.strip()}%"
        q = q.filter(
            models.Cliente.nombre_completo.ilike(termino) |
            models.Cliente.telefono.ilike(termino)
        )
    return q.all()