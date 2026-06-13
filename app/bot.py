"""
Módulo del Bot de WhatsApp con Registro de Clientes Completo.
Gestiona el flujo de conversación automatizada con los clientes a través de Twilio.
Mantiene el estado de la conversación en memoria por cada número telefónico.
"""

from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models

# ── Estado de conversación en memoria por número telefónico ─────────────────────────
# { telefono: {"paso": "menu"|..., "productos": [...], "pedido_temporal": {...}} }
sesiones = {}


def obtener_catalogo() -> list:
    """Recupera los productos disponibles excluyendo descontinuados."""
    with Session(engine) as db:
        return db.query(models.Producto).filter(
            ~models.Producto.nombre.startswith("[DESCONTINUADO]")
        ).all()


def verificar_registro_cliente(telefono: str) -> models.Cliente | None:
    """Verifica si el cliente existe y tiene sus datos de delivery completos."""
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(
            models.Cliente.telefono == telefono
        ).first()
        
        # Si no existe o le faltan datos críticos, consideramos que no está registrado
        if not cliente or not cliente.direccion_exacta or cliente.nombre_completo == "Cliente WhatsApp":
            return None
        return cliente


def actualizar_o_crear_cliente(telefono: str, datos: dict) -> int:
    """Crea o actualiza los datos del cliente en Supabase."""
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(
            models.Cliente.telefono == telefono
        ).first()
        
        if not cliente:
            cliente = models.Cliente(telefono=telefono)
            db.add(cliente)
            
        if "nombre" in datos:
            cliente.nombre_completo = datos["nombre"]
        if "direccion" in datos:
            cliente.direccion_exacta = datos["direccion"]
        if "referencia" in datos:
            cliente.referencia_ubicacion = datos["referencia"]
            
        db.commit()
        db.refresh(cliente)
        return cliente.id


def registrar_pedido(telefono: str, producto_id: int, cantidad: int) -> tuple[bool, float | str]:
    """Crea el pedido restando inventario y activando alertas si es necesario."""
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
        if not cliente:
            return False, "Cliente no registrado en el sistema."

        producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
        if not producto:
            return False, "Producto no encontrado."
            
        if (producto.stock_actual or 0) < cantidad:
            return False, f"Solo hay {producto.stock_actual} unidades disponibles."

        # Descuento de stock y alerta de stock crítico
        producto.stock_actual -= cantidad
        if producto.stock_actual <= (producto.stock_minimo or 10):
            producto.alerta_roja = True

        total = (producto.precio_venta or 0) * cantidad

        nuevo_pedido = models.Pedido(
            cliente_id=cliente.id,
            total_pedido=total,
            estado_logistico="recibido",
            estado_pago="sin pagar",
            requiere_agente=False
        )
        db.add(nuevo_pedido)
        db.flush()

        detalle = models.DetallePedido(
            pedido_id=nuevo_pedido.id,
            producto_id=producto_id,
            cantidad=cantidad,
        )
        db.add(detalle)
        db.commit()
        return True, total


def menu_principal() -> str:
    return (
        "👋 *Bienvenido a Smart-Liquor* 🍷\n\n"
        "¿Qué deseas hacer?\n\n"
        "1️⃣ Ver catálogo\n"
        "2️⃣ Hacer un pedido 🛒\n"
        "3️⃣ Info de delivery\n"
        "4️⃣ Métodos de pago\n\n"
        "👉 Responde con el número."
    )


def procesar_mensaje(cuerpo_mensaje: str, telefono: str = "default") -> str:
    """Motor principal del flujo del chatbot indexado por número telefónico."""
    mensaje  = cuerpo_mensaje.strip()
    msg_bajo = mensaje.lower()
    response = MessagingResponse()
    msg      = response.message()

    # Inicializar sesión única por número telefónico
    if telefono not in sesiones:
        sesiones[telefono] = {"paso": "menu", "datos_registro": {}}

    sesion = sesiones[telefono]
    paso   = sesion.get("paso", "menu")

    # Palabras clave globales de reinicio
    if msg_bajo in ["hola", "inicio", "menu", "menú", "cancelar"]:
        sesiones[telefono] = {"paso": "menu", "datos_registro": {}}
        msg.body(menu_principal())
        return str(response)

    # ── PASO: MENÚ PRINCIPAL ───────────────────────────────────
    if paso == "menu":
        if mensaje == "1":
            try:
                productos = obtener_catalogo()
                if not productos:
                    msg.body("😔 Catálogo vacío por el momento. Intenta más tarde.")
                else:
                    texto = "🛒 *CATÁLOGO SMART-LIQUOR* 🍷\n━━━━━━━━━━━━\n\n"
                    for i, p in enumerate(productos, 1):
                        stock_ok = (p.stock_actual or 0) > (p.stock_minimo or 10)
                        estado   = "✅" if stock_ok else "⚠️ Últimas"
                        texto   += f"{i}. *{p.nombre}*\n"
                        texto   += f"   💰 S/ {p.precio_venta:.2f}  {estado}\n\n"
                    texto += "Escribe *2* para iniciar tu pedido."
                    msg.body(texto)
            except Exception as ex:
                msg.body("😔 Error al cargar catálogo. Intenta más tarde.")

        elif mensaje == "2":
            # VALIDACIÓN CRÍTICA: ¿El cliente ya tiene su perfil listo en Supabase?
            cliente = verificar_registro_cliente(telefono)
            
            if not cliente:
                # Si no está registrado, lo enviamos al embudo de registro primero
                sesion["paso"] = "registrando_nombre"
                msg.body(
                    "📝 *Registro de Cliente Nuevo*\n\n"
                    "Para poder procesar tus pedidos y gestionar el delivery en Chincha, necesitamos registrar tus datos.\n\n"
                    "👉 Por favor, escribe tu *Nombre y Apellido* completo:"
                )
            else:
                # Si ya está registrado, va directo al flujo de compra tradicional
                ir_a_seleccion_productos(msg, sesion, telefono)

        elif mensaje == "3":
            msg.body(
                "🚚 *DELIVERY Y HORARIOS*\n\n"
                "📍 *Chincha:* Grocio Prado, Sunampe, Pueblo Nuevo, Chincha Alta.\n\n"
                "⏰ Lun - Dom: 9:00 AM - 11:00 PM\n"
                "💵 Costo: S/3.00 - S/7.00 según sector.\n\n"
                "Escribe *INICIO* para regresar."
            )

        elif mensaje == "4":
            msg.body(
                "💳 *MÉTODOS DE PAGO*\n\n"
                "✅ Yape / Plin: *999 999 999*\n"
                "✅ Efectivo contra entrega\n"
                "✅ Tarjetas de Crédito/Débito en ruta\n\n"
                "Escribe *INICIO* para regresar."
            )
        else:
            msg.body("🤔 No entendí la opción.\n\n" + menu_principal())

    # ── FLUJO DE REGISTRO: PASO 1 (NOMBRE) ──────────────────────
    elif paso == "registrando_nombre":
        if len(mensaje) < 4:
            msg.body("⚠️ Por favor ingresa un nombre válido y completo:")
        else:
            sesion["datos_registro"]["nombre"] = mensaje
            sesion["paso"] = "registrando_direccion"
            msg.body(
                f"¡Gracias, *{mensaje}*!\n\n"
                "🏡 Ahora ingresa tu *Dirección Exacta* para el delivery\n"
                "_(Ejemplo: Av. Victor Fajardo 345, Sunampe)_:"
            )

    # ── FLUJO DE REGISTRO: PASO 2 (DIRECCIÓN) ───────────────────
    elif paso == "registrando_direccion":
        if len(mensaje) < 6:
            msg.body("⚠️ Proporciona una dirección más detallada para evitar confusiones:")
        else:
            sesion["datos_registro"]["direccion"] = mensaje
            sesion["paso"] = "registrando_referencia"
            msg.body(
                "📍 Por último, una *Referencia de tu ubicación*\n"
                "_(Ejemplo: Frente al colegio o a espaldas de la plaza)_:"
            )

    # ── FLUJO DE REGISTRO: PASO 3 (REFERENCIA Y GUARDADO) ───────
    elif paso == "registrando_referencia":
        if len(mensaje) < 4:
            msg.body("⚠️ Por favor añade una referencia más clara:")
        else:
            sesion["datos_registro"]["referencia"] = mensaje
            
            # Guardamos los datos recolectados directamente en Supabase
            actualizar_o_crear_cliente(telefono, sesion["datos_registro"])
            
            # Registro exitoso, pasamos de inmediato al catálogo de productos
            msg.body("✅ ¡Registro completado con éxito en Smart-Liquor!\n\n Procedamos con tu compra.")
            ir_a_seleccion_productos(msg, sesion, telefono)

    # ── PASO: ELIGIENDO PRODUCTO ───────────────────────────────
    elif paso == "eligiendo_producto":
        productos = sesion.get("productos", [])
        try:
            idx = int(mensaje) - 1
            if 0 <= idx < len(productos):
                prod_id, prod_nombre, prod_precio = productos[idx]
                sesion.update({
                    "paso": "eligiendo_cantidad",
                    "producto_id": prod_id,
                    "producto_nombre": prod_nombre,
                    "producto_precio": prod_precio,
                })
                msg.body(
                    f"🍾 Seleccionaste: *{prod_nombre}*\n"
                    f"💰 Precio: S/ {prod_precio:.2f}\n\n"
                    "¿Cuántas unidades o cajas deseas?\n"
                    "👉 Responde con un número (ej: 2):"
                )
            else:
                msg.body(f"⚠️ Número inválido. Elige entre 1 y {len(productos)}.")
        except ValueError:
            msg.body(f"⚠️ Envía solo el número del licor. Elige entre 1 y {len(productos)}.")

    # ── PASO: ELIGIENDO CANTIDAD ───────────────────────────────
    elif paso == "eligiendo_cantidad":
        try:
            cantidad = int(mensaje)
            if cantidad <= 0:
                raise ValueError()

            total = sesion["producto_price"] = sesion["producto_precio"] * cantidad
            sesion.update({
                "paso": "confirmando",
                "cantidad": cantidad,
                "total": total,
            })
            msg.body(
                f"📦 *Resumen de tu pedido:*\n\n"
                f"🍾 {sesion['producto_nombre']}\n"
                f"🔢 Cantidad: {cantidad}\n"
                f"💰 Total a pagar: S/ {total:.2f}\n\n"
                "¿Confirmas el envío?\n"
                "👉 Responde *SI* para confirmar\n"
                "👉 Responde *NO* para cancelar"
            )
        except ValueError:
            msg.body("⚠️ Por favor escribe un número entero válido (ej: 3):")

    # ── PASO: CONFIRMANDO PEDIDO ───────────────────────────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            try:
                ok, resultado = registrar_pedido(telefono, sesion["producto_id"], sesion["cantidad"])
                # Limpiamos el estado volviendo al menú
                sesiones[telefono] = {"paso": "menu", "datos_registro": {}}

                if ok:
                    msg.body(
                        f"✅ *¡Pedido registrado!*\n━━━━━━━━━━━━━━\n"
                        f"El pedido ya se envió al panel logístico de Chincha.\n\n"
                        f"💰 Total: S/ {resultado:.2f}\n\n"
                        "🚚 El repartidor se comunicará contigo al llegar. ¡Gracias por elegir Smart-Liquor!"
                    )
                else:
                    msg.body(f"⚠️ No pudimos procesarlo: {resultado}\n\nEscribe *INICIO* para reintentar.")
            except Exception as ex:
                sesiones[telefono] = {"paso": "menu", "datos_registro": {}}
                msg.body("😔 Hubo un inconveniente al procesar el pedido. Por favor, reintenta.")

        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono] = {"paso": "menu", "datos_registro": {}}
            msg.body("❌ Pedido cancelado.\n\n" + menu_principal())
        else:
            msg.body("👉 Responde *SI* para confirmar tu orden o *NO* para anularla.")

    return str(response)


def ir_a_seleccion_productos(msg, sesion, telefono):
    """Función auxiliar para listar productos y cambiar de estado."""
    try:
        productos = obtener_catalogo()
        if not productos:
            msg.body("😔 No hay licores disponibles en este instante.")
        else:
            texto = "🛒 *¿Qué deseas pedir hoy?*\n\n"
            for i, p in enumerate(productos, 1):
                texto += f"{i}. {p.nombre} — S/ {p.precio_venta:.2f}\n"
            texto += "\n👉 Responde con el *número* del producto:"
            
            sesion["paso"] = "eligiendo_producto"
            sesion["productos"] = [(p.id, p.nombre, p.precio_venta) for p in productos]
            msg.body(texto)
    except Exception as ex:
        msg.body("😔 Error al desplegar la lista de licores. Escribe *INICIO*.")