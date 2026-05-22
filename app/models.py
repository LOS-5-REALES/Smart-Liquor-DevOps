# app/models.py
"""
Módulo de modelos de la base de datos (ORM).

Define la estructura de las tablas de la base de datos y las relaciones
entre ellas utilizando SQLAlchemy.
"""

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Producto(Base):
    """
    Representa un producto en el catálogo del sistema.

    Attributes:
        id (int): Identificador único del producto.
        nombre (str): Nombre comercial.
        marca (str): Marca del fabricante.
        precio_venta (float): Precio final para el cliente.
        costo_compra (float): Costo de adquisición al proveedor.
        stock_actual (int): Cantidad de unidades físicas disponibles.
        stock_minimo (int): Umbral para disparar la alerta de reabastecimiento.
        alerta_roja (bool): Indicador automático de que el stock es crítico.
        detalles (Relationship): Lista de DetallePedido vinculados a este producto.
    """
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    marca = Column(String)
    precio_venta = Column(Float)
    costo_compra = Column(Float)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=10)
    alerta_roja = Column(Boolean, default=False)

    detalles = relationship("DetallePedido", back_populates="producto")


class Cliente(Base):
    """
    Representa a un cliente que interactúa con el sistema vía WhatsApp.

    Attributes:
        id (int): Identificador único del cliente.
        telefono (str): Número de teléfono celular (usado como identificador único en WhatsApp).
        nombre_completo (str): Nombre del cliente.
        direccion_exacta (str): Dirección de entrega.
        referencia_ubicacion (str): Referencias adicionales para el repartidor.
        pedidos (Relationship): Lista de pedidos realizados por este cliente.
    """
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    telefono = Column(String, unique=True, nullable=False)
    nombre_completo = Column(String)
    direccion_exacta = Column(String)
    referencia_ubicacion = Column(String)

    pedidos = relationship("Pedido", back_populates="cliente")


class Pedido(Base):
    """
    Representa una orden de compra realizada por un cliente.

    Attributes:
        id (int): Identificador único de la orden.
        cliente_id (int): Clave foránea que enlaza con la tabla clientes.
        fecha_hora (DateTime): Marca de tiempo de la creación del pedido.
        total_pedido (float): Suma total en dinero de todos los items del pedido.
        estado_logistico (str): Fase del pedido (ej. recibido, en camino, entregado).
        estado_pago (str): Estado financiero del pedido.
        cliente (Relationship): Objeto del cliente asociado.
        items (Relationship): Lista de los detalles de productos que componen el pedido.
    """
    __tablename__ = "pedidos"
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    fecha_hora = Column(DateTime, server_default=func.now())
    total_pedido = Column(Float, default=0.0)
    estado_logistico = Column(String, default="recibido")
    estado_pago = Column(String, default="sin pagar")

    cliente = relationship("Cliente", back_populates="pedidos")
    items = relationship("DetallePedido", back_populates="pedido")


class DetallePedido(Base):
    """
    Representa un item individual (línea) dentro de un pedido.

    Sirve como tabla intermedia con datos adicionales entre Pedidos y Productos.

    Attributes:
        id (int): Identificador único del detalle.
        pedido_id (int): Clave foránea del pedido al que pertenece.
        producto_id (int): Clave foránea del producto solicitado.
        cantidad (int): Número de unidades solicitadas de este producto.
        pedido (Relationship): Objeto del pedido padre.
        producto (Relationship): Objeto del producto referenciado.
    """
    __tablename__ = "detalle_pedidos"
    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer)

    pedido = relationship("Pedido", back_populates="items")
    producto = relationship("Producto", back_populates="detalles")


class EntradaSuministro(Base):
    """
    Representa un registro histórico del ingreso de nueva mercadería al almacén.

    Attributes:
        id (int): Identificador único del suministro.
        producto_id (int): Clave foránea del producto que se está reabasteciendo.
        cantidad_ingresada (int): Cantidad de unidades físicas que se sumaron al stock.
        fecha (DateTime): Marca de tiempo automática de cuándo ocurrió el ingreso.
    """
    __tablename__ = "suministros"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad_ingresada = Column(Integer)
    fecha = Column(DateTime, server_default=func.now())