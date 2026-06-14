"""
Módulo del Bot de WhatsApp con Registro por Saltos de Línea (Enter).
Optimizado para capturar datos en un solo mensaje estructurado por líneas,
asegurando el commit en la base de datos y previniendo congelamientos.
"""

from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models
import traceback

# Estado de conversación en memoria
sesiones = {}


def obtener_catalogo() -> list:
    """Recupera los productos disponibles excluyendo descontinuados."""
    with Session(engine) as db:
        return db.query(models.Producto).filter(
            ~models.Producto.nombre.startswith("[DESCONTINUADO]")
        ).all()


def verificar_registro_cliente(telefono: str) -> bool:
    """Verifica si el cliente existe y tiene sus datos completos."""
    with Session(engine) as db:
        cliente = db.query(models.Cliente).filter(
            models.Cliente.telefono == telefono
        ).first()
        if not cliente or not cliente.direccion_exacta or cliente.nombre_completo == "Cliente WhatsApp":
            return False
        return True


def registrar_cliente_completo(telefono: str, texto_registro: str) -> bool:
    """
    Parsea el mensaje dividiendo el texto línea por línea (usando saltos de línea).
    Elimina la necesidad de usar barras diagonales u otros símbolos molestos.
    """
    print(f"[LOG SERVER] Texto crudo recibido para procesar:\n{texto_registro}")

    # Separamos el bloque de texto por cada salto de línea y limpiamos espacios vacíos
    partes = [p.strip() for p in texto_registro.splitlines() if p.strip()]
    
    print(f"[LOG SERVER] Líneas útiles detectadas: {partes} | Cantidad: {len(partes)}")

    # Validamos que el cliente haya ingresado al menos las 3 líneas obligatorias
    if len(partes) < 3 or not partes[0] or not partes[1] or not partes[2]:
        print(f"[REGISTRO FALLIDO] No se encontraron las 3 líneas requeridas en el mensaje.")
        return False

    # Asignamos el orden estricto de las líneas
    nombre, direccion, referencia = partes[0], partes[1], partes[2]

    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
            if not cliente:
                cliente = models.Cliente(telefono=telefono)
                db.add(cliente)
            
            cliente.nombre_completo = nombre
            cliente.direccion_exacta = direccion
            cliente.referencia_ubicacion = referencia
            
            db.commit()  # Persistencia inmediata en la base de datos de Supabase
            print(f"[REGISTRO EXITOSO] Cliente {telefono} guardado correctamente en Supabase.")
            return True
    except Exception as e:
        print(f"[ERROR BD] Falló la inserción transaccional: {e}")
        traceback.print_exc()
        return False


def registrar_pedido(telefono: str, producto_id: int, cantidad: int) -> tuple[bool, float | str]:
    """Crea el pedido de forma transaccional reduciendo stock."""
    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
            if not cliente:
                return False, "Cliente no encontrado."

            producto = db.query(models.Producto).filter(models.Producto.id == producto_id).first()
            if not producto:
                return False, "Producto no encontrado."
                
            if (producto.stock_actual or 0) < cantidad:
                return False, f"Solo hay {producto.stock_actual} unidades."

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
    except Exception as e:
        print(f"[ERROR PEDIDO] No se pudo guardar el pedido: {e}")
        return False, "Error interno del servidor."


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
    mensaje  = cuerpo_mensaje.strip()
    msg_bajo = mensaje.lower()
    response = MessagingResponse()
    msg      = response.message()

    if telefono not in sesiones:
        sesiones[telefono] = {"paso": "menu"}

    sesion = sesiones[telefono]
    paso   = sesion.get("paso", "menu")

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
                    msg.body("😔 Catálogo vacío por el momento.")
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
                msg.body("😔 Error al cargar catálogo.")

        elif mensaje == "2":
            if not verificar_registro_cliente(telefono):
                sesion["paso"] = "esperando_registro_unico"
                msg.body(
                    "📝 *REGISTRO DE CLIENTE NUEVO* 🏡\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "Para poder procesar tus pedidos y gestionar el delivery en Chincha, necesitamos tus datos.\n\n"
                    "👉 Por favor, envíanos tu información en un *SOLO MENSAJE* escribiendo cada dato en una **línea diferente** (presionando la tecla Enter en tu teclado):\n\n"
                    "✍️ *Formato requerido:*\n"
                    "Línea 1: Nombre Completo\n"
                    "Línea 2: Dirección Exacta\n"
                    "Línea 3: Referencia de tu casa\n\n"
                    "💡 *Ejemplo exacto a enviar:* \n"
                    "Carlos Mendoza Ruiz\n"
                    "Av. Benavides 412, Chincha Alta\n"
                    "Frente al Grifo Primax"
                )
            else:
                ir_a_seleccion_productos(msg, sesion)
        else:
            msg.body("🤔 Opción no válida.\n\n" + menu_principal())

    # ── PASO: CAPTURA Y VALIDACIÓN DEL REGISTRO ────────────────
    elif paso == "esperando_registro_unico":
        exito = registrar_cliente_completo(telefono, mensaje)
        if exito:
            ir_a_seleccion_productos(msg, sesion)
        else:
            msg.body(
                "⚠️ *No pudimos procesar el registro.*\n\n"
                "Por favor, asegúrate de enviar tus 3 datos utilizando **líneas separadas** (presionando Enter):\n\n"
                "1️⃣ Tu Nombre Completo\n"
                "2️⃣ Tu Dirección Exacta\n"
                "3️⃣ Una Referencia Cercana"
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
                    "¿Cuántas unidades deseas? (Ejemplo: 2)"
                )
            else:
                msg.body(f"⚠️ Selecciona una opción válida entre 1 y {len(productos)}.")
        except ValueError:
            msg.body("⚠️ Envía solo el número de la opción.")

    # ── PASO: SELECCIÓN DE CANTIDAD ────────────────────────────
    elif paso == "eligiendo_cantidad":
        try:
            cantidad = int(mensaje)
            if cantidad <= 0:
                raise ValueError()

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
                "¿Confirmas el envío?\n"
                "👉 Responde *SI* o *NO*"
            )
        except ValueError:
            msg.body("⚠️ Por favor escribe un número entero válido (ej: 2):")

    # ── PASO: CONFIRMACIÓN DEL PEDIDO ─────────────────────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            ok, resultado = registrar_pedido(telefono, sesion["producto_id"], sesion["cantidad"])
            sesiones[telefono] = {"paso": "menu"}

            if ok:
                msg.body(
                    f"✅ *¡Pedido registrado!*\n\n"
                    f"💰 Total a pagar: S/ {resultado:.2f}\n\n"
                    "🚚 Tu pedido ya figura en el panel administrativo de Chincha. ¡Gracias!"
                )
            else:
                msg.body(f"⚠️ Error: {resultado}\n\nEscribe *INICIO*.")
        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono] = {"paso": "menu"}
            msg.body("❌ Pedido cancelado.\n\n" + menu_principal())
        else:
            msg.body("👉 Responde *SI* para confirmar o *NO* para anular.")

    return str(response)


def ir_a_seleccion_productos(msg, sesion):
    """Muestra el catálogo y cambia el estado para recibir la elección del licor."""
    try:
        productos = obtener_catalogo()
        if not productos:
            msg.body("😔 No hay licores disponibles en este instante.")
        else:
            texto = "✅ *¡Registro completado con éxito!* 🎉\n\n🛒 *¿Qué deseas pedir hoy?*\n\n"
            for i, p in enumerate(productos, 1):
                texto += f"{i}. {p.nombre} — S/ {p.precio_venta:.2f}\n"
            texto += "\n👉 Responde con el *número* del producto:"
            
            sesion["paso"] = "eligiendo_producto"
            sesion["productos"] = [(p.id, p.nombre, p.precio_venta) for p in productos]
            msg.body(texto)
    except Exception:
        msg.body("😔 Error al desplegar licores.")