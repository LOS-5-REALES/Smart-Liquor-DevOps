# app/bot.py
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models

# ── Estado de conversación en memoria ─────────────────────────
# { telefono: {"paso": "menu"|"eligiendo_producto"|"eligiendo_cantidad", "producto_id": int} }
sesiones = {}


def obtener_catalogo():
    with Session(engine) as db:
        return db.query(models.Producto).filter(
            ~models.Producto.nombre.startswith("[DESCONTINUADO]")
        ).all()


def obtener_o_crear_cliente(telefono: str):
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(
            models.Cliente.telefono == telefono
        ).first()
        if not cliente:
            cliente = models.Cliente(
                telefono=telefono,
                nombre_completo="Cliente WhatsApp",
            )
            db.add(cliente)
            db.commit()
            db.refresh(cliente)
        return cliente.id, cliente.nombre_completo


def registrar_pedido(cliente_id: int, producto_id: int, cantidad: int):
    with Session(engine) as db:
        producto = db.query(models.Producto).filter(
            models.Producto.id == producto_id
        ).first()
        if not producto:
            return False, "Producto no encontrado."
        if (producto.stock_actual or 0) < cantidad:
            return False, f"Solo hay {producto.stock_actual} unidades disponibles."

        producto.stock_actual -= cantidad
        if producto.stock_actual <= (producto.stock_minimo or 10):
            producto.alerta_roja = True

        total = (producto.precio_venta or 0) * cantidad

        nuevo_pedido = models.Pedido(
            cliente_id=cliente_id,
            total_pedido=total,
            estado_logistico="recibido",
            estado_pago="sin pagar",
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


def menu_principal():
    return (
        "👋 *Bienvenido a Smart-Liquor* 🍷\n\n"
        "¿Qué deseas hacer?\n\n"
        "1️⃣ Ver catálogo\n"
        "2️⃣ Hacer un pedido\n"
        "3️⃣ Info de delivery\n"
        "4️⃣ Métodos de pago\n\n"
        "👉 Responde con el número."
    )


def procesar_mensaje(cuerpo_mensaje: str):
    """
    Bot con flujo guiado — el cliente solo responde con números.
    El estado se guarda en memoria (sesiones).
    """
    # Twilio envía el número como "whatsapp:+51999..."
    # Como no recibimos el teléfono aquí usamos un key genérico
    # Para estado por usuario necesitarías pasar el From desde main_bot.py
    telefono = "default"

    mensaje  = cuerpo_mensaje.strip()
    msg_bajo = mensaje.lower()
    response = MessagingResponse()
    msg      = response.message()

    # Inicializar sesión si no existe
    if telefono not in sesiones:
        sesiones[telefono] = {"paso": "menu"}

    sesion = sesiones[telefono]
    paso   = sesion.get("paso", "menu")

    # ── Palabras que siempre resetean al menú ─────────────────
    if msg_bajo in ["hola", "inicio", "menu", "menú", "cancelar",
                    "buenos días", "buenas tardes", "buenas noches"]:
        sesiones[telefono] = {"paso": "menu"}
        msg.body(menu_principal())
        return str(response)

    # ── PASO: menú principal ───────────────────────────────────
    if paso == "menu":
        if mensaje == "1":
            try:
                productos = obtener_catalogo()
                if not productos:
                    msg.body("😔 Catálogo vacío. Intenta más tarde.")
                else:
                    texto = "🛒 *CATÁLOGO SMART-LIQUOR* 🍷\n━━━━━━━━━━━━\n\n"
                    for i, p in enumerate(productos, 1):
                        stock_ok = (p.stock_actual or 0) > (p.stock_minimo or 10)
                        estado   = "✅" if stock_ok else "⚠️ Últimas"
                        texto   += f"{i}. *{p.nombre}*\n"
                        texto   += f"   💰 S/ {p.precio_venta:.2f}  {estado}\n\n"
                    texto += "Escribe *2* para hacer un pedido."
                    msg.body(texto)
            except Exception as ex:
                print(f"[BOT ERROR catalogo] {ex}")
                msg.body("😔 Error al cargar catálogo. Intenta más tarde.")

        elif mensaje == "2":
            try:
                productos = obtener_catalogo()
                if not productos:
                    msg.body("😔 No hay productos disponibles.")
                else:
                    texto = "🛒 ¿Qué deseas pedir?\n\n"
                    for i, p in enumerate(productos, 1):
                        texto += f"{i}. {p.nombre} — S/ {p.precio_venta:.2f}\n"
                    texto += "\n👉 Responde con el *número* del producto."
                    sesiones[telefono] = {
                        "paso": "eligiendo_producto",
                        "productos": [(p.id, p.nombre, p.precio_venta) for p in productos]
                    }
                    msg.body(texto)
            except Exception as ex:
                print(f"[BOT ERROR pedido] {ex}")
                msg.body("😔 Error. Escribe *INICIO* para reintentar.")

        elif mensaje == "3":
            msg.body(
                "🚚 *DELIVERY*\n\n"
                "📍 *Ica:* Centro y zonas aledañas (15-30 min)\n"
                "📍 *Chincha:* Grocio Prado, Sunampe, Pueblo Nuevo\n\n"
                "⏰ Lun - Dom: 9:00 AM - 11:00 PM\n"
                "💵 Costo: S/3.00 - S/7.00 según zona\n\n"
                "Escribe *INICIO* para volver al menú."
            )

        elif mensaje == "4":
            msg.body(
                "💳 *MÉTODOS DE PAGO*\n\n"
                "✅ Yape / Plin: 999 999 999\n"
                "✅ Efectivo contra entrega\n"
                "✅ Tarjeta VISA/Mastercard\n\n"
                "Escribe *INICIO* para volver al menú."
            )

        else:
            msg.body(
                "🤔 No entendí eso.\n\n"
                + menu_principal()
            )

    # ── PASO: eligiendo producto ───────────────────────────────
    elif paso == "eligiendo_producto":
        productos = sesion.get("productos", [])
        try:
            idx = int(mensaje) - 1
            if 0 <= idx < len(productos):
                prod_id, prod_nombre, prod_precio = productos[idx]
                sesiones[telefono] = {
                    "paso": "eligiendo_cantidad",
                    "producto_id":     prod_id,
                    "producto_nombre": prod_nombre,
                    "producto_precio": prod_precio,
                }
                msg.body(
                    f"✅ Seleccionaste: *{prod_nombre}*\n"
                    f"💰 Precio: S/ {prod_precio:.2f}\n\n"
                    "¿Cuántas unidades deseas?\n"
                    "👉 Responde con un número (ej: 2)\n\n"
                    "Escribe *CANCELAR* para volver al menú."
                )
            else:
                msg.body(f"⚠️ Número inválido. Elige entre 1 y {len(productos)}.")
        except ValueError:
            msg.body(f"⚠️ Responde solo con el número del producto.\nElige entre 1 y {len(productos)}.")

    # ── PASO: eligiendo cantidad ───────────────────────────────
    elif paso == "eligiendo_cantidad":
        try:
            cantidad     = int(mensaje)
            prod_id      = sesion["producto_id"]
            prod_nombre  = sesion["producto_nombre"]
            prod_precio  = sesion["producto_precio"]

            if cantidad <= 0:
                raise ValueError()

            total = prod_precio * cantidad
            sesiones[telefono] = {
                "paso":             "confirmando",
                "producto_id":      prod_id,
                "producto_nombre":  prod_nombre,
                "producto_precio":  prod_precio,
                "cantidad":         cantidad,
                "total":            total,
            }
            msg.body(
                f"📦 *Resumen de tu pedido:*\n\n"
                f"🍾 {prod_nombre}\n"
                f"🔢 Cantidad: {cantidad}\n"
                f"💰 Total: S/ {total:.2f}\n\n"
                "¿Confirmas?\n"
                "👉 Responde *SI* para confirmar\n"
                "👉 Responde *NO* para cancelar"
            )
        except ValueError:
            msg.body("⚠️ Escribe solo el número de unidades. Ejemplo: _2_")

    # ── PASO: confirmando pedido ───────────────────────────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            try:
                cliente_id, _ = obtener_o_crear_cliente(telefono)
                ok, resultado = registrar_pedido(
                    cliente_id,
                    sesion["producto_id"],
                    sesion["cantidad"],
                )
                sesiones[telefono] = {"paso": "menu"}

                if ok:
                    msg.body(
                        f"✅ *¡Pedido confirmado!*\n\n"
                        f"🍾 {sesion['producto_nombre']}\n"
                        f"🔢 x{sesion['cantidad']}\n"
                        f"💰 Total: S/ {resultado:.2f}\n\n"
                        "📱 Un administrador se contactará pronto.\n\n"
                        "Escribe *INICIO* para hacer otro pedido."
                    )
                else:
                    msg.body(
                        f"⚠️ No se pudo completar: {resultado}\n\n"
                        "Escribe *INICIO* para intentar de nuevo."
                    )
            except Exception as ex:
                print(f"[BOT ERROR confirmar] {ex}")
                sesiones[telefono] = {"paso": "menu"}
                msg.body("😔 Error al registrar. Contacta al administrador.")

        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono] = {"paso": "menu"}
            msg.body("❌ Pedido cancelado.\n\n" + menu_principal())

        else:
            msg.body("👉 Responde *SI* para confirmar o *NO* para cancelar.")

    else:
        sesiones[telefono] = {"paso": "menu"}
        msg.body(menu_principal())

    return str(response)