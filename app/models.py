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
    """
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    marca = Column(String)
    precio_venta = Column(Float, nullable=False)  # Sincronizado NOT NULL
    costo_compra = Column(Float)
    stock_actual = Column(Integer, default=0)
    stock_minimo = Column(Integer, default=0)    # Sincronizado con DEFAULT 0 de tu BD
    alerta_roja = Column(Boolean, default=False)

    detalles = relationship("DetallePedido", back_populates="producto")


class Cliente(Base):
    """
    Representa a un cliente que interactúa con el sistema vía WhatsApp.
    """
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True, index=True)
    telefono = Column(String, nullable=False)
    nombre_completo = Column(String, nullable=False)  # Sincronizado NOT NULL
    direccion_exacta = Column(String)
    referencia_ubicacion = Column(String)

    pedidos = relationship("Pedido", back_populates="cliente")


class Pedido(Base):
    """
    Representa una orden de compra realizada por un cliente.
    """
    __tablename__ = "pedidos"
    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"))
    fecha_hora = Column(DateTime, server_default=func.now())
    total_pedido = Column(Float, default=0.0)
    estado_logistico = Column(String, default="recibido")
    estado_pago = Column(String, default="sin pagar")
    # 🚨 COLUMNA ADICIONADA: Requerida por la lógica de transacciones y el script SQL de Supabase
    requiere_agente = Column(Boolean, nullable=False, default=False)
    nota_cliente = Column(String)  # Sincronizado text

    cliente = relationship("Cliente", back_populates="pedidos")
    items = relationship("DetallePedido", back_populates="pedido")


class DetallePedido(Base):
    """
    Representa un item individual (línea) dentro de un pedido.
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
    """
    __tablename__ = "suministros"
    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad_ingresada = Column(Integer)
    fecha = Column(DateTime, server_default=func.now())