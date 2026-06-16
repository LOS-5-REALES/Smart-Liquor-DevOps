"""
Módulo del Bot de WhatsApp con Registros Ultra Robusto basado en Extracción por Índices.
Optimizado para capturar datos en un solo mensaje identificando los bloques de texto
mediante búsquedas directas de palabras clave, asegurando el commit en Supabase y
un flujo conversacional fluido con el cliente.
"""

import traceback
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models

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
    Parsea el mensaje buscando las etiquetas 'Nombre:', 'Dirección:' y 'Referencia:'.
    Corta los bloques de texto de manera exacta, aislando asteriscos o saltos corruptos.
    """
    print(f"[LOG SERVER] Texto crudo recibido para procesar:\n{texto_registro}")

    # Normalizamos temporalmente a minúsculas solo para buscar las posiciones de las etiquetas
    texto_bajo = texto_registro.lower()

    # Validación estricta de palabras clave indispensables
    if "nombre" not in texto_bajo or "direc" not in texto_bajo or "referencia" not in texto_bajo:
        print("[REGISTRO FALLIDO] Faltan etiquetas indispensables en el mensaje.")
        return False

    try:
        # 1. EXTRAER NOMBRE: Todo lo que esté entre 'nombre:' y la palabra 'dirección/direccion/dir'
        inicio_nombre = texto_bajo.find("nombre:") + len("nombre:")
        fin_nombre = texto_bajo.find("direc")
        nombre_raw = texto_registro[inicio_nombre:fin_nombre]
        nombre = nombre_raw.replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        # 2. EXTRAER DIRECCIÓN: Todo lo que esté entre la etiqueta de dirección y 'referencia'
        inicio_dir_raiz = texto_bajo.find("direc")
        texto_recortado_dir = texto_bajo[inicio_dir_raiz:]
        index_dos_puntos_dir = texto_recortado_dir.find(":")
        
        inicio_dir_real = inicio_dir_raiz + index_dos_puntos_dir + 1
        fin_dir = texto_bajo.find("referencia")
        direccion_raw = texto_registro[inicio_dir_real:fin_dir]
        direccion = direccion_raw.replace("*", "").strip().splitlines()[0].strip()

        # 3. EXTRAER REFERENCIA: Todo lo que esté desde 'referencia:' hasta el final del mensaje
        inicio_ref = texto_bajo.find("referencia:") + len("referencia:")
        referencia_raw = texto_registro[inicio_ref:]
        referencia = referencia_raw.replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        print(f"[LOG PARSED SUCCESS] Nombre: '{nombre}' | Dirección: '{direccion}' | Referencia: '{referencia}'")

        # Validación final de que los campos no se hayan extraído vacíos
        if not nombre or not direccion or not referencia:
            print("[REGISTRO FALLIDO] Datos incompletos tras la segmentación por texto.")
            return False

        # Guardado directo en la base de datos de Supabase
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
            if not cliente:
                cliente = models.Cliente(telefono=telefono)
                db.add(cliente)
            
            cliente.nombre_completo = nombre
            cliente.direccion_exacta = direccion
            cliente.referencia_ubicacion = referencia
            
            db.commit()  # Confirmación síncrona en base de datos
            print(f"[REGISTRO EXITOSO] Cliente {telefono} guardado correctamente en Supabase.")
                
            return True

    except Exception as e:
        print(f"[ERROR EXCEPCIÓN BD] Falló el guardado del cliente: {e}")
        traceback.print_exc()
        return False


def registrar_pedido(telefono: str, producto_id: int, cantidad: int) -> tuple[bool, float | str]:
    """Crea el pedido de forma transaccional reduciendo stock en base al esquema double precision."""
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

            # Al ser double precision, forzamos float nativo de Python de forma segura
            total = float(producto.precio_venta or 0.0) * cantidad

            nuevo_pedido = models.Pedido(
                cliente_id=cliente.id,
                total_pedido=total,
                estado_logistico="recibido",
                estado_pago="sin pagar",
                requiere_agente=False
            )
            db.add(nuevo_pedido)
            db.flush()

            # IMPORTANTE: Asegúrate de que en tu archivo models.py, este modelo 
            # apunte a la tabla 'detalle_pedidos' (singular según tu script SQL)
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
        traceback.print_exc()
        return False, "Error interno del servidor."


def menu_principal() -> str:
    return (
        "👋 *¡Bienvenido a Smart-Liquor!* 🍷\n"
        "Tu distribuidora de confianza en Chincha.\n\n"
        "¿Qué te provoca llevar hoy?\n\n"
        "1️⃣ Explora nuestro catálogo ✨\n"
        "2️⃣ Iniciar un pedido nuevo 🛒\n"
        "3️⃣ Cobertura y Delivery 🚚\n"
        "4️⃣ Cuentas y Métodos de pago 💳\n\n"
        "👉 Escribe solo el *número* de tu opción favorita."
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
                        precio   = float(p.precio_venta or 0.0)
                        texto   += f"{i}. *{p.nombre}*\n"
                        texto   += f"   💰 S/ {precio:.2f}  {estado}\n\n"
                    texto += "Escribe *2* para iniciar tu pedido."
                    msg.body(texto)
            except Exception:
                msg.body("😔 Error al cargar catálogo.")
            return str(response)

        elif mensaje == "2":
            if not verificar_registro_cliente(telefono):
                sesion["paso"] = "esperando_registro_unico"
                msg.body(
                    "✨ *¡Estás a un paso de tu pedido!* ✨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Para llevar tus licores favoritos hasta la puerta de tu casa en Chincha, por favor envíanos tus datos de entrega en un solo mensaje siguiendo este formato simple:\n\n"
                    "📍 *Nombre:* Tu Nombre y Apellido\n"
                    "📍 *Dirección:* Calle, Número o Distrito\n"
                    "📍 *Referencia:* Color de fachada, negocio cercano, etc.\n\n"
                    "💡 *Ejemplo rápido:*\n"
                    "Nombre: Carlos Mendoza Ramos\n"
                    "Dirección: Jr. Melchorita 124, Grocio Prado\n"
                    "Referencia: Frente a la plaza principal, portón marrón"
                )
            else:
                ir_a_seleccion_productos(msg, sesion)
            return str(response)
        else:
            msg.body("🤔 Opción no válida.\n\n" + menu_principal())
            return str(response)

    # ── PASO: CAPTURA Y VALIDACIÓN DEL REGISTRO ────────────────
    elif paso == "esperando_registro_unico":
        exito = registrar_cliente_completo(telefono, mensaje)
        if exito:
            sesion["paso"] = "eligiendo_producto"
            ir_a_seleccion_productos(msg, sesion)
        else:
            msg.body(
                "⚠️ *No pudimos procesar tus datos.*\n\n"
                "Por favor, asegúrate de escribir las palabras clave seguidas de los dos puntos (*:*):\n\n"
                "👉 *Nombre:* Tu Nombre\n"
                "👉 *Dirección:* Tu Dirección\n"
                "👉 *Referencia:* Tu Referencia"
            )
        return str(response)

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
                    "producto_precio": float(prod_precio),
                })
                msg.body(
                    f"🍾 Seleccionaste: *{prod_nombre}*\n"
                    f"💰 Precio: S/ {float(prod_precio):.2f}\n\n"
                    "¿Cuántas unidades deseas? (Ejemplo: 2)"
                )
            else:
                msg.body(f"⚠️ Selecciona una opción válida entre 1 y {len(productos)}.")
        except ValueError:
            msg.body("⚠️ Envía solo el número de la opción.")
        return str(response)

    # ── PASO: SELECCIÓN DE CANTIDAD ────────────────────────────
    elif paso == "eligiendo_cantidad":
        try:
            cantidad = int(mensaje)
            if cantidad <= 0:
                raise ValueError()

            total = float(sesion["producto_precio"]) * cantidad
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
        return str(response)

    # ── PASO: CONFIRMACIÓN DEL PEDIDO ─────────────────────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            ok, resultado = registrar_pedido(telefono, sesion["producto_id"], sesion["cantidad"])
            sesiones[telefono] = {"paso": "menu"}

            if ok:
                msg.body(
                    f"✅ *¡Pedido registrado!*\n\n"
                    f"💰 Total a pagar: S/ {float(resultado):.2f}\n\n"
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

    return str(response)


def ir_a_seleccion_productos(msg, sesion):
    """Muestra el catálogo y cambia el estado para recibir la elección del licor."""
    try:
        productos = obtener_catalogo()
        if not productos:
            msg.body("😔 No hay licores disponibles en este instante.")
        else:
            texto = (
                "✅ *¡Datos guardados con éxito!* 🎉\n"
                "Ya quedaste registrado en nuestro sistema.\n\n"
                "🛒 *¿Qué deseas pedir hoy?*\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            for i, p in enumerate(productos, 1):
                # Sincronizado nativamente con double precision (float)
                precio = float(p.precio_venta or 0.0)
                texto += f"{i}. {p.nombre} — S/ {precio:.2f}\n"
            texto += "\n👉 Responde con el *número* del producto para agregarlo a tu carrito:"
            
            sesion["paso"] = "eligiendo_producto"
            sesion["productos"] = [(int(p.id), str(p.nombre), float(p.precio_venta or 0.0)) for p in productos]
            msg.body(texto)
    except Exception as e:
        print(f"[ERROR EN ir_a_seleccion_productos]: {e}")
        traceback.print_exc()
        msg.body("😔 Error al desplegar licores.")