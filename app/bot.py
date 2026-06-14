"""
Módulo del Bot de WhatsApp con Registro Eficiente (Ahorro de Créditos).
Pide todos los datos de delivery en un solo mensaje estructurado para mitigar
gastos redundantes en la API de Twilio y evitar congelamientos en el flujo.
"""

from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models

# ── Estado de conversación en memoria por número telefónico ─────────────────────────
sesiones = {}


def obtener_catalogo() -> list:
    """Recupera los productos disponibles excluyendo los descontinuados."""
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
        
        # Si no existe, no tiene dirección o mantiene el genérico, requiere registro
        if not cliente or not cliente.direccion_exacta or cliente.nombre_completo == "Cliente WhatsApp":
            return None
        return cliente


def registrar_cliente_completo(telefono: str, texto_registro: str) -> bool:
    """
    Parsea el mensaje único del cliente y persiste los datos reales en Supabase.
    Formato esperado: Nombre / Dirección / Referencia
    """
    # Intentamos separar prioritariamente por barras diagonales
    partes = [p.strip() for p in texto_registro.split("/")]
    
    # Salvaguarda por si el cliente usó comas en lugar de barras
    if len(partes) < 3:
        partes = [p.strip() for p in texto_registro.split(",")]
        
    # Si no se logran extraer los 3 datos mínimos obligatorios, falla la validación
    if len(partes) < 3 or not partes[0] or not partes[1] or not partes[2]:
        return False

    nombre_comp, direccion, referencia = partes[0], partes[1], partes[2]

    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
        if not cliente:
            cliente = models.Cliente(telefono=telefono)
            db.add(cliente)
            
        cliente.nombre_completo = nombre_comp
        cliente.direccion_exacta = direccion
        cliente.referencia_ubicacion = referencia
        db.commit()
        return True


def registrar_pedido(telefono: str, producto_id: int, cantidad: int) -> tuple[bool, float | str]:
    """Crea el pedido restando inventario y activando alertas si es necesario."""
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
        if not cliente:
            return False, "Cliente no encontrado en el sistema."

        producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
        if not producto:
            return False, "Producto no encontrado."
            
        if (producto.stock_actual or 0) < cantidad:
            return False, f"Solo hay {producto.stock_actual} unidades disponibles."

        # Descuento de inventario y bandera de stock crítico
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
        "👉 Responde con el número de la opción."
    )


def procesar_mensaje(cuerpo_mensaje: str, telefono: str = "default") -> str:
    """Motor principal del flujo automatizado indexado de forma multiusuario."""
    mensaje  = cuerpo_mensaje.strip()
    msg_bajo = mensaje.lower()
    response = MessagingResponse()
    msg      = response.message()

    # Inicializar estado aislado por número de teléfono
    if telefono not in sesiones:
        sesiones[telefono] = {"paso": "menu"}

    sesion = sesiones[telefono]
    paso   = sesion.get("paso", "menu")

    # Comandos globales de escape o reinicio
    if msg_bajo in ["hola", "inicio", "menu", "menú", "cancelar"]:
        sesiones[telefono] = {"paso": "menu"}
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
            except Exception:
                msg.body("😔 Error al cargar catálogo. Intenta más tarde.")

        elif mensaje == "2":
            # Verificación inmediata contra la base de datos de Supabase
            cliente = verificar_registro_cliente(telefono)
            
            if not cliente:
                # Modificamos el paso a un único estado de captura masiva para ahorrar saldo de Twilio
                sesion["paso"] = "esperando_registro_unico"
                msg.body(
                    "📝 *REGISTRO DE CLIENTE NUEVO* 🏡\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Para poder procesar tus pedidos y gestionar el delivery en Chincha, necesitamos tus datos.\n\n"
                    "👉 Por favor, envíanos tu información en un *SOLO MENSAJE* separado por barras diagonales *( / )* con el siguiente formato:\n\n"
                    "*Nombre Completo / Dirección Exacta / Referencia*\n\n"
                    "💡 *Ejemplo exacto a enviar:* \n"
                    "_Jesús Loza Yataco / Av. Emancipación 345, Sunampe / Al costado de una antena_"
                )
            else:
                ir_a_seleccion_productos(msg, sesion)

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
                "✅ Tarjetas en ruta\n\n"
                "Escribe *INICIO* para regresar."
            )
        else:
            msg.body("🤔 No entendí la opción.\n\n" + menu_principal())

    # ── PASO: CAPTURA EFICIENTE DE DATOS (UN SOLO MENSAJE) ───
    elif paso == "esperando_registro_unico":
        exito = registrar_cliente_completo(telefono, mensaje)
        if exito:
            # Datos guardados perfectamente en Supabase, pasamos directo al catálogo
            msg.body("✅ ¡Registro completado y guardado en la Base de Datos con éxito!")
            ir_a_seleccion_productos(msg, sesion)
        else:
            msg.body(
                "⚠️ *Formato de registro inválido.*\n\n"
                "Por favor, vuelve a intentarlo asegurándote de usar las barras diagonales *( / )* para dividir los tres datos:\n\n"
                "👉 _Nombre Completo / Dirección Exacta / Referencia_"
            )

    # ── PASO: SELECCIÓN DE PRODUCTO ────────────────────────────
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
                    "👉 Responde con un número entero (ej: 2):"
                )
            else:
                msg.body(f"⚠️ Número inválido. Selecciona una opción entre 1 y {len(productos)}.")
        except ValueError:
            msg.body(f"⚠️ Por favor, envía solo el número de la opción (1 al {len(productos)}).")

    # ── PASO: SELECCIÓN DE CANTIDAD ────────────────────────────
    elif paso == "eligiendo_cantidad":
        try:
            cantidad = int(mensaje)
            if cantidad <= 0:
                raise ValueError()

            # ✨ SOLUCIÓN AL BUG: Corregido de 'producto_price' a 'producto_precio' para evitar excepciones
            total = sesion["producto_precio"] * cantidad
            
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
                "¿Confirmas el envío de tu orden?\n"
                "👉 Responde *SI* para confirmar\n"
                "👉 Responde *NO* para cancelar"
            )
        except ValueError:
            msg.body("⚠️ Entrada inválida. Por favor escribe un número entero válido (ej: 3):")

    # ── PASO: CONFIRMACIÓN DEL PEDIDO ─────────────────────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            try:
                ok, resultado = registrar_pedido(telefono, sesion["producto_id"], sesion["cantidad"])
                # Liberar memoria de la sesión volviendo al estado inicial
                sesiones[telefono] = {"paso": "menu"}

                if ok:
                    msg.body(
                        f"✅ *¡Pedido registrado!*\n━━━━━━━━━━━━━━\n"
                        f"El pedido ya se envió al panel logístico de Chincha.\n\n"
                        f"💰 Total: S/ {resultado:.2f}\n\n"
                        "🚚 El repartidor se comunicará contigo al llegar. ¡Gracias por elegir Smart-Liquor!"
                    )
                else:
                    msg.body(f"⚠️ No pudimos procesar tu solicitud: {resultado}\n\nEscribe *INICIO* para volver a empezar.")
            except Exception:
                sesiones[telefono] = {"paso": "menu"}
                msg.body("😔 Hubo un inconveniente interno al procesar el pedido. Por favor, reintenta escribiendo *INICIO*.")

        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono] = {"paso": "menu"}
            msg.body("❌ Pedido cancelado.\n\n" + menu_principal())
        else:
            msg.body("👉 Responde *SI* para confirmar tu orden o *NO* para anularla de forma definitiva.")

    return str(response)


def ir_a_seleccion_productos(msg, sesion):
    """Función auxiliar centralizada para recuperar catálogo y renderizar opciones."""
    try:
        productos = obtener_catalogo()
        if not productos:
            msg.body("😔 No hay licores disponibles en este instante. Intenta más tarde.")
        else:
            texto = "🛒 *¿Qué deseas pedir hoy?*\n\n"
            for i, p in enumerate(productos, 1):
                texto += f"{i}. {p.nombre} — S/ {p.precio_venta:.2f}\n"
            texto += "\n👉 Responde con el *número* del licor que deseas:"
            
            sesion["paso"] = "eligiendo_producto"
            sesion["productos"] = [(p.id, p.nombre, p.precio_venta) for p in productos]
            msg.body(texto)
    except Exception:
        msg.body("😔 Error al desplegar la lista de licores. Escribe *INICIO* para reintentar.")