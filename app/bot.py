"""
Módulo del Bot de WhatsApp con Registros Ultra Robusto basado en Extracción por Índices.
Optimizado para redirigir al usuario al Catálogo Digital Web mediante enlaces inteligentes,
atrapando los retornos transaccionales empaquetados y asegurando el stock en Supabase.
"""

import traceback
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from database import engine
import models

# Estado de conversación en memoria
sesiones = {}

# ── CONFIGURACIÓN DEL ENTORNO DIGITAL (PRODUCCIÓN AZURE) ─────────────────
# IP pública estática asignada a la Máquina Virtual de Azure vía Terraform
BASE_URL_WEB = "http://57.156.66.168:8000"  


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
    texto_bajo = texto_registro.lower()

    if "nombre" not in texto_bajo or "direc" not in texto_bajo or "referencia" not in texto_bajo:
        print("[REGISTRO FALLIDO] Faltan etiquetas indispensables en el mensaje.")
        return False

    try:
        # 1. EXTRAER NOMBRE
        inicio_nombre = texto_bajo.find("nombre:") + len("nombre:")
        fin_nombre = texto_bajo.find("direc")
        nombre_raw = texto_registro[inicio_nombre:fin_nombre]
        nombre = nombre_raw.replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        # 2. EXTRAER DIRECCIÓN
        inicio_dir_raiz = texto_bajo.find("direc")
        texto_recortado_dir = texto_bajo[inicio_dir_raiz:]
        index_dos_puntos_dir = texto_recortado_dir.find(":")
        inicio_dir_real = inicio_dir_raiz + index_dos_puntos_dir + 1
        fin_dir = texto_bajo.find("referencia")
        direccion_raw = texto_registro[inicio_dir_real:fin_dir]
        direccion = direccion_raw.replace("*", "").strip().splitlines()[0].strip()

        # 3. EXTRAER REFERENCIA
        inicio_ref = texto_bajo.find("referencia:") + len("referencia:")
        referencia_raw = texto_registro[inicio_ref:]
        referencia = referencia_raw.replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        print(f"[LOG PARSED SUCCESS] Nombre: '{nombre}' | Dirección: '{direccion}' | Referencia: '{referencia}'")

        if not nombre or not direccion or not referencia:
            print("[REGISTRO FALLIDO] Datos incompletos tras la segmentación por texto.")
            return False

        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
            if not cliente:
                cliente = models.Cliente(telefono=telefono)
                db.add(cliente)
            
            cliente.nombre_completo = nombre
            cliente.direccion_exacta = direccion
            cliente.referencia_ubicacion = referencia
            
            db.commit()
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
        "1️⃣ Abrir nuestro Catálogo Digital (Solo ver) ✨\n"
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

    # Sanitizar número (limpiar prefijos de twilio si vienen adjuntos)
    telefono_limpio = telefono.replace("whatsapp:", "").replace("+", "").strip()

    if telefono_limpio not in sesiones:
        sesiones[telefono_limpio] = {"paso": "menu"}

    sesion = sesiones[telefono_limpio]
    paso   = sesion.get("paso", "menu")

    # 🚨 INTERCEPTOR EXCLUSIVO: Retorno automatizado desde la App Web (Flet)
    if mensaje.startswith("PEDIDO_WEB:"):
        try:
            datos_raw = mensaje.replace("PEDIDO_WEB:", "").strip()
            partes = datos_raw.split("|")
            prod_id = int(partes[0].split("=")[1])
            cantidad = int(partes[1].split("=")[1])

            with Session(engine) as db:
                producto = db.query(models.Producto).filter(models.Producto.id == prod_id).first()
                if not producto:
                    msg.body("⚠️ El producto seleccionado ya no está disponible. Por favor, escribe *MENU*.")
                    return str(response)
                
                total = float(producto.precio_venta or 0.0) * cantidad
                
                sesiones[telefono_limpio] = {
                    "paso": "confirmando",
                    "producto_id": prod_id,
                    "producto_nombre": producto.nombre,
                    "producto_precio": float(producto.precio_venta),
                    "cantidad": cantidad,
                    "total": total
                }

                msg.body(
                    f"📦 *Resumen de tu Pedido Web:*\n\n"
                    f"🍾 {producto.nombre}\n"
                    f"🔢 Cantidad: {cantidad}\n"
                    f"💰 Total a pagar: S/ {total:.2f}\n\n"
                    "¿Confirmamos el envío a tu dirección?\n"
                    "👉 Responde *SI* o *NO*"
                )
                return str(response)
        except Exception as e:
            print(f"[ERROR PARSEANDO RETORNO WEB]: {e}")
            msg.body("⚠️ Ocurrió un error al procesar tu carrito web. Por favor escribe *MENU* para reiniciar.")
            return str(response)

    # ── CONTROL LOGÍSTICO DE NAVEGACIÓN COMÚN ─────────────────
    if msg_bajo in ["hola", "inicio", "menu", "menú", "cancelar"]:
        sesiones[telefono_limpio] = {"paso": "menu"}
        msg.body(menu_principal())
        return str(response)

    # ── PASO: MENÚ PRINCIPAL ───────────────────────────────────
    if paso == "menu":
        # 1️⃣ OPCIÓN 1: SOLO VER EL CATÁLOGO (Sin restricciones de registro)
        if mensaje == "1":
            msg.body(generar_enlace_catalogo(telefono_limpio, modo="ver"))
            return str(response)
        
        # 2️⃣ OPCIÓN 2: INICIAR UN PEDIDO NUEVO (Validación obligatoria)
        elif mensaje == "2":
            if not verificar_registro_cliente(telefono_limpio):
                sesion["paso"] = "esperando_registro_unico"
                msg.body(
                    "✨ *¡Estás a un paso de tu pedido!* ✨\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Para llevar tus licores favoritos hasta tu casa en Chincha, envíanos tus datos de entrega en un solo mensaje siguiendo este formato:\n\n"
                    "📍 *Nombre:* Tu Nombre y Apellido\n"
                    "📍 *Dirección:* Calle, Número o Distrito\n"
                    "📍 *Referencia:* Color de fachada, negocio cercano, etc.\n\n"
                    "💡 *Ejemplo rápido:*\n"
                    "Nombre: Carlos Mendoza Ramos\n"
                    "Dirección: Jr. Melchorita 124, Grocio Prado\n"
                    "Referencia: Frente a la plaza principal, portón marrón"
                )
            else:
                msg.body(generar_enlace_catalogo(telefono_limpio, modo="pedido"))
            return str(response)
        
        else:
            msg.body("🤔 Opción no válida.\n\n" + menu_principal())
            return str(response)

    # ── PASO: CAPTURA Y VALIDACIÓN DEL REGISTRO (SOLO ENTRADA DESDE OPCIÓN 2) ──
    elif paso == "esperando_registro_unico":
        exito = registrar_cliente_completo(telefono_limpio, mensaje)
        if exito:
            msg.body(generar_enlace_catalogo(telefono_limpio, modo="pedido"))
        else:
            msg.body(
                "⚠️ *No pudimos procesar tus datos.*\n\n"
                "Por favor, asegúrate de escribir las palabras clave seguidas de los dos puntos (*:*):\n\n"
                "👉 *Nombre:* Tu Nombre\n"
                "👉 *Dirección:* Tu Dirección\n"
                "👉 *Referencia:* Tu Referencia"
            )
        return str(response)

    # ── PASO: CONFIRMACIÓN DEL PEDIDO (VÍA RETORNO WEB) ────────
    elif paso == "confirmando":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            ok, resultado = registrar_pedido(telefono_limpio, sesion["producto_id"], sesion["cantidad"])
            sesiones[telefono_limpio] = {"paso": "menu"}

            if ok:
                msg.body(
                    f"✅ *¡Pedido registrado con éxito!* 🎉\n\n"
                    f"💰 Total a pagar: S/ {float(resultado):.2f}\n\n"
                    "🚚 Tu pedido ya figura en tiempo real en nuestro Panel Administrativo de Chincha. ¡Muchas gracias por tu preferencia!"
                )
            else:
                msg.body(f"⚠️ Error: {resultado}\n\nEscribe *INICIO*.")
        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono_limpio] = {"paso": "menu"}
            msg.body("❌ Pedido cancelado.\n\n" + menu_principal())
        else:
            msg.body("👉 Responde *SI* para confirmar o *NO* para anular.")
        return str(response)

    return str(response)


def generar_enlace_catalogo(telefono: str, modo: str = "ver") -> str:
    """Construye la respuesta interactiva con el enlace dinámico y limpio según el modo."""
    nombre_cliente = "Cliente"
    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(models.Cliente.telefono == telefono).first()
            if cliente and cliente.nombre_completo and cliente.nombre_completo != "Cliente WhatsApp":
                nombre_cliente = cliente.nombre_completo.split()[0]
    except Exception:
        pass

    # Inyección matemática del modo en el parámetro query string para que Flet lo interprete
    url_inteligente = f"{BASE_URL_WEB}/?telefono={telefono}&modo={modo}"
    
    if modo == "pedido":
        sesiones[telefono] = {"paso": "esperando_carrito_web"}
        return (
            f"🛒 *¡HOLA {nombre_cliente.upper()}! ARMEMOS TU PEDIDO* 🍷\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Elige tus productos, ajusta las cantidades en el carrito interactivo y presiona confirmar abajo:\n\n"
            f"{url_inteligente}\n\n"
            "💡 Al darle a 'Confirmar Pedido', regresarás aquí automáticamente para agendar tu entrega rápida."
        )
    else:
        # Modo Lectura: No muta el paso de la conversación, el cliente puede seguir navegando el menú
        return (
            f"✨ *¡HOLA {nombre_cliente.upper()}! AQUÍ TIENES EL INVENTARIO* 🍾\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Explora nuestros más de 130 licores y precios actuales disponibles para entrega en Chincha haciendo clic aquí:\n\n"
            f"{url_inteligente}\n\n"
            "💡 Nota: Este enlace es exclusivamente de modo lectura. Para comprar, selecciona la opción 2 en el menú principal."
        )