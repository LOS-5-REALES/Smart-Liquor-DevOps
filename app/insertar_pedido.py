from sqlalchemy.orm import Session
from database import SessionLocal 
import models
from models import Producto, Cliente, Pedido, DetallePedido

def crear_pedido_que_genera_alerta():
    db = SessionLocal()
    try:
        print("--- 📡 Iniciando Pedido de Agotamiento de Stock ---")
        
        # 1. Buscar la Cachina específicamente
        producto = db.query(Producto).filter(models.Producto.nombre == 'Cachina').first()
        if not producto:
            print("❌ No se encontró el producto 'Cachina'.")
            return

        # 2. Buscar o crear Cliente
        cliente = db.query(Cliente).filter(models.Cliente.telefono == "999000111").first()
        if not cliente:
            cliente = Cliente(
                nombre_completo="Licorería El Paso - Chincha",
                telefono="999000111",
                direccion_exacta="Av. Benavides 456",
                referencia_ubicacion="Frente al Grifo"
            )
            db.add(cliente)
            db.flush()

        # 3. Calcular cantidad para dejarlo en Stock Bajo (Menos de 10)
        # Si tiene 35, vamos a pedir 28 para que queden 7.
        cantidad_a_pedir = (producto.stock_actual - producto.stock_minimo) + 3 
        
        if producto.stock_actual < cantidad_a_pedir:
            print(f"⚠️ No hay suficiente stock para generar la prueba. Stock actual: {producto.stock_actual}")
            return

        # 4. Crear el Pedido
        total = producto.precio_venta * cantidad_a_pedir
        nuevo_pedido = Pedido(
            cliente_id=cliente.id,
            total_pedido=total,
            estado_logistico="recibido"
        )
        db.add(nuevo_pedido)
        db.flush()

        # 5. Crear el Detalle
        detalle = DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=producto.id,
            cantidad=cantidad_a_pedir
        )
        db.add(detalle)

        # 6. Restar el Stock (Esto disparará la alerta visual en la UI)
        producto.stock_actual -= cantidad_a_pedir
        print(f"📉 Venta realizada: {cantidad_a_pedir} unidades.")
        print(f"🚨 NUEVO STOCK DE {producto.nombre}: {producto.stock_actual} (ALERTA ACTIVADA)")

        db.commit()
        print(f"✅ PEDIDO ID: {nuevo_pedido.id} REGISTRADO CON ÉXITO")

    except Exception as e:
        db.rollback()
        print(f"❌ ERROR: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    crear_pedido_que_genera_alerta()