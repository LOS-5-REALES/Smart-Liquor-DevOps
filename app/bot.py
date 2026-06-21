# app/bot.py
"""
Motor del Bot de WhatsApp — Smart Liquor
Flujo: Menú → Registro (si nuevo) → URL Catálogo Web → Confirmación
Guarda historial de mensajes en mensajes_whatsapp para el panel del agente.
"""

import traceback
from datetime import datetime, timezone
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from database import engine
import models

sesiones     = {}
BASE_URL_WEB = "http://57.156.66.168:8000"
NUMERO_BOT   = "14155238886"


# ── Helpers de historial ──────────────────────────────────────

def guardar_mensaje(telefono: str, mensaje: str, origen: str = "cliente"):
    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            nuevo = models.MensajeWhatsapp(
                telefono=telefono,
                cliente_id=cliente.id if cliente else None,
                mensaje=mensaje,
                origen=origen,
            )
            db.add(nuevo)
            if cliente:
                cliente.ultimo_mensaje = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        print(f"[ERROR guardar_mensaje] {e}")
        traceback.print_exc()


def cliente_en_modo_agente(telefono: str) -> bool:
    try:
        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            return c.modo_agente if c else False
    except Exception:
        return False


def desactivar_modo_agente(telefono: str):
    try:
        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if c and c.modo_agente:
                c.modo_agente = False
                db.commit()
                print(f"[BOT] Modo agente desactivado para {telefono}")
    except Exception as e:
        print(f"[ERROR desactivar_modo_agente] {e}")


def activar_modo_agente(telefono: str):
    try:
        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if c:
                c.modo_agente    = True
                c.ultimo_mensaje = datetime.now(timezone.utc)
                db.commit()
    except Exception as e:
        print(f"[ERROR activar_modo_agente] {e}")


# ── Helpers de DB ─────────────────────────────────────────────

def verificar_registro_cliente(telefono: str) -> bool:
    with Session(engine) as db:
        c = db.query(models.Cliente).filter(
            models.Cliente.telefono == telefono
        ).first()
        if not c or not c.direccion_exacta or c.nombre_completo == "Cliente WhatsApp":
            return False
        return True


def registrar_cliente_completo(telefono: str, texto: str) -> bool:
    print(f"[LOG] Texto registro:\n{texto}")
    texto_bajo = texto.lower()
    if "nombre" not in texto_bajo or "direc" not in texto_bajo or "referencia" not in texto_bajo:
        return False
    try:
        inicio_nombre = texto_bajo.find("nombre:") + len("nombre:")
        fin_nombre    = texto_bajo.find("direc")
        nombre = texto[inicio_nombre:fin_nombre].replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        inicio_dir_raiz = texto_bajo.find("direc")
        texto_recortado = texto_bajo[inicio_dir_raiz:]
        idx_dos_puntos  = texto_recortado.find(":")
        inicio_dir_real = inicio_dir_raiz + idx_dos_puntos + 1
        fin_dir         = texto_bajo.find("referencia")
        direccion = texto[inicio_dir_real:fin_dir].replace("*", "").strip().splitlines()[0].strip()

        inicio_ref = texto_bajo.find("referencia:") + len("referencia:")
        referencia = texto[inicio_ref:].replace(":", "").replace("*", "").strip().splitlines()[0].strip()

        print(f"[LOG] Nombre='{nombre}' | Dir='{direccion}' | Ref='{referencia}'")

        if not nombre or not direccion or not referencia:
            return False

        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if not c:
                c = models.Cliente(telefono=telefono, nombre_completo="Cliente WhatsApp")
                db.add(c)
            c.nombre_completo      = nombre
            c.direccion_exacta     = direccion
            c.referencia_ubicacion = referencia
            c.ultimo_mensaje       = datetime.now(timezone.utc)
            db.commit()
            return True
    except Exception as e:
        print(f"[ERROR registro] {e}")
        traceback.print_exc()
        return False


def registrar_pedidos_multiples(telefono: str, items: list) -> tuple:
    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if not cliente:
                return False, "Cliente no encontrado."

            total_general = 0.0
            detalles_confirmados = []

            for item in items:
                prod = db.query(models.Producto).filter(
                    models.Producto.id == item["producto_id"]
                ).first()
                if not prod:
                    return False, f"Producto ID {item['producto_id']} no encontrado."
                if (prod.stock_actual or 0) < item["cantidad"]:
                    return False, f"Stock insuficiente para {prod.nombre}."
                subtotal = float(prod.precio_venta or 0) * item["cantidad"]
                total_general += subtotal
                detalles_confirmados.append({
                    "prod": prod, "cantidad": item["cantidad"], "subtotal": subtotal
                })

            nuevo_pedido = models.Pedido(
                cliente_id=cliente.id,
                total_pedido=total_general,
                estado_logistico="recibido",
                estado_pago="sin pagar",
                requiere_agente=False
            )
            db.add(nuevo_pedido)
            db.flush()

            for d in detalles_confirmados:
                d["prod"].stock_actual -= d["cantidad"]
                if d["prod"].stock_actual <= (d["prod"].stock_minimo or 10):
                    d["prod"].alerta_roja = True
                db.add(models.DetallePedido(
                    pedido_id=nuevo_pedido.id,
                    producto_id=d["prod"].id,
                    cantidad=d["cantidad"],
                ))

            db.commit()
            return True, total_general

    except IntegrityError as e:
        if "duplicate key" in str(e).lower():
            print("[⚠️ BD] Llave duplicada. Reparando secuencia...")
            try:
                with Session(engine) as db_fix:
                    db_fix.execute(text(
                        "SELECT setval('pedidos_id_seq', "
                        "COALESCE((SELECT MAX(id) FROM pedidos), 0) + 1, false);"
                    ))
                    db_fix.commit()
                print("[⚙️ SECUENCIA REPARADA] Reintentando...")
                return registrar_pedidos_multiples(telefono, items)
            except Exception as fix_err:
                print(f"[ERROR FIX] {fix_err}")
        return False, "Error de duplicidad en Base de Datos."

    except Exception as e:
        print(f"[ERROR PEDIDO MULTI] {e}")
        traceback.print_exc()
        return False, "Error interno del servidor."


# ── Textos ────────────────────────────────────────────────────

def menu_principal() -> str:
    return (
        "👋 *¡Bienvenido a Smart-Liquor!* 🍷\n"
        "Tu distribuidora de confianza en Chincha.\n\n"
        "¿Qué deseas hacer?\n\n"
        "1️⃣ Ver catálogo de productos\n"
        "2️⃣ Hacer un pedido\n"
        "3️⃣ Hablar con un agente\n\n"
        "👉 Escribe solo el *número* de tu opción."
    )


def nombre_cliente_corto(telefono: str) -> str:
    try:
        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if c and c.nombre_completo and c.nombre_completo != "Cliente WhatsApp":
                return c.nombre_completo.split()[0].upper()
    except Exception:
        pass
    return "CLIENTE"


def generar_url_catalogo(telefono: str, modo: str) -> str:
    nombre = nombre_cliente_corto(telefono)
    url    = f"{BASE_URL_WEB}/?telefono={telefono}&modo={modo}"

    if modo == "pedido":
        sesiones[telefono] = {"paso": "esperando_carrito_web"}
        return (
            f"🛒 *¡HOLA {nombre}! ARMEMOS TU PEDIDO* 🍷\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Elige tus productos en el catálogo, ajusta las cantidades "
            "y presiona *Confirmar Pedido*. Luego vuelves aquí para finalizar:\n\n"
            f"⬇️ Toca el enlace:\n"
            f"\n"
            f"{url}.com\n\n"
            f"\n"
            "💡 Al confirmar en la web, recibirás un resumen aquí para aprobarlo."
        )
    else:
        return (
            f"✨ *¡HOLA {nombre}! NUESTRO CATÁLOGO* 🍾\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "Explora todos nuestros productos y precios:\n\n"
            f"⬇️ Toca el enlace:\n"
            f"\n"
            f"{url}.com\n\n"
            f"\n"
            "💡 Este enlace es solo de lectura. Para comprar elige la opción *2*."
        )


# ── Motor principal ───────────────────────────────────────────

def procesar_mensaje(cuerpo_mensaje: str, telefono: str = "default") -> str:
    mensaje  = cuerpo_mensaje.strip()
    msg_bajo = mensaje.lower()
    response = MessagingResponse()
    msg      = response.message()

    telefono_limpio = telefono.replace("whatsapp:", "").replace("+", "").strip()
    if not telefono_limpio:
        telefono_limpio = "default"

    # ── Guardar mensaje del cliente en historial ──────────────
    guardar_mensaje(telefono_limpio, mensaje, origen="cliente")

    # ── MENU desactiva modo agente y responde normalmente ─────
    if msg_bajo in ["menu", "menú", "inicio"]:
        desactivar_modo_agente(telefono_limpio)
        sesiones[telefono_limpio] = {"paso": "menu"}
        respuesta_texto = menu_principal()
        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")
        return str(response)

    # ── Si está en modo agente, el bot no responde ────────────
    if cliente_en_modo_agente(telefono_limpio):
        print(f"[BOT] Cliente {telefono_limpio} en modo agente — bot silenciado.")
        msg.body("")
        return str(response)

    if telefono_limpio not in sesiones:
        sesiones[telefono_limpio] = {"paso": "menu"}

    sesion = sesiones[telefono_limpio]
    paso   = sesion.get("paso", "menu")
    respuesta_texto = ""

    # ── Interceptor pedido web ────────────────────────────────
    if "PEDIDO_WEB:" in mensaje:
        try:
            lineas = [l.strip() for l in mensaje.split("\n") if "PEDIDO_WEB:" in l]
            items  = []
            resumen_lines = []

            for linea in lineas:
                datos    = linea.replace("PEDIDO_WEB:", "").strip()
                partes   = datos.split("|")
                prod_id  = int(partes[0].split("=")[1])
                cantidad = int(partes[1].split("=")[1])

                with Session(engine) as db:
                    prod = db.query(models.Producto).filter(
                        models.Producto.id == prod_id
                    ).first()
                    if prod:
                        items.append({"producto_id": prod_id, "cantidad": cantidad})
                        subtotal = float(prod.precio_venta or 0) * cantidad
                        resumen_lines.append(
                            f"🍾 {prod.nombre} x{cantidad} = S/ {subtotal:.2f}"
                        )

            if not items:
                respuesta_texto = "⚠️ No se encontraron productos válidos. Escribe *MENU* para reintentar."
                msg.body(respuesta_texto)
                guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")
                return str(response)

            with Session(engine) as db:
                total_estimado = 0.0
                for item in items:
                    p = db.query(models.Producto).filter(
                        models.Producto.id == item["producto_id"]
                    ).first()
                    if p:
                        total_estimado += float(p.precio_venta or 0) * item["cantidad"]

            sesiones[telefono_limpio] = {
                "paso":    "confirmando_multi",
                "items":   items,
                "resumen": resumen_lines,
                "total":   total_estimado,
            }

            resumen_txt     = "\n".join(resumen_lines)
            respuesta_texto = (
                f"📦 *Resumen de tu pedido:*\n\n"
                f"{resumen_txt}\n\n"
                f"💰 *Total: S/ {total_estimado:.2f}*\n\n"
                "¿Confirmamos el envío a tu dirección registrada?\n"
                "👉 Responde *SI* para confirmar o *NO* para cancelar."
            )
            msg.body(respuesta_texto)
            guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")
        except Exception as e:
            print(f"[ERROR PEDIDO WEB] {e}")
            traceback.print_exc()
            respuesta_texto = "⚠️ Error al procesar tu carrito. Escribe *MENU* para reintentar."
            msg.body(respuesta_texto)
            guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")
        return str(response)

    # ── Reset con hola/cancelar ───────────────────────────────
    if msg_bajo in ["hola", "cancelar", "buenos días", "buenas tardes",
                    "buenas noches", "buenas"]:
        sesiones[telefono_limpio] = {"paso": "menu"}
        respuesta_texto = menu_principal()
        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")
        return str(response)

    # ── MENÚ PRINCIPAL ────────────────────────────────────────
    if paso == "menu":
        if mensaje == "1":
            respuesta_texto = generar_url_catalogo(telefono_limpio, "ver")

        elif mensaje == "2":
            if not verificar_registro_cliente(telefono_limpio):
                sesion["paso"]  = "esperando_registro"
                respuesta_texto = (
                    "✨ *¡Estás a un paso de tu pedido!*\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "Para entregarte tus pedidos necesitamos tus datos.\n"
                    "Envíalos en un solo mensaje con este formato:\n\n"
                    "📍 *Nombre:* Tu Nombre y Apellido\n"
                    "📍 *Dirección:* Calle, Número, Distrito\n"
                    "📍 *Referencia:* Color de fachada, negocio cercano\n\n"
                    "💡 *Ejemplo:*\n"
                    "Nombre: Carlos Mendoza\n"
                    "Dirección: Jr. Melchorita 124, Grocio Prado\n"
                    "Referencia: Frente a la plaza, portón marrón"
                )
            else:
                respuesta_texto = generar_url_catalogo(telefono_limpio, "pedido")

        elif mensaje == "3":
            activar_modo_agente(telefono_limpio)
            sesiones[telefono_limpio] = {"paso": "menu"}
            respuesta_texto = (
                "👨‍💼 *Conectando con un agente...*\n\n"
                "Un administrador de Smart-Liquor se pondrá en contacto "
                "contigo en breve para atenderte personalmente.\n\n"
                "⏰ Horario: Lunes a Domingo 9:00 AM - 11:00 PM\n\n"
                "Escribe *MENU* si deseas volver al bot."
            )
        else:
            respuesta_texto = "🤔 Opción no válida.\n\n" + menu_principal()

        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")

    # ── REGISTRO NUEVO CLIENTE ────────────────────────────────
    elif paso == "esperando_registro":
        exito = registrar_cliente_completo(telefono_limpio, mensaje)
        if exito:
            respuesta_texto = generar_url_catalogo(telefono_limpio, "pedido")
        else:
            respuesta_texto = (
                "⚠️ *No pudimos leer tus datos.*\n\n"
                "Asegúrate de usar exactamente este formato:\n\n"
                "Nombre: Tu Nombre\n"
                "Dirección: Tu Dirección\n"
                "Referencia: Tu Referencia"
            )
        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")

    # ── CONFIRMACIÓN MULTI-PRODUCTO ───────────────────────────
    elif paso == "confirmando_multi":
        if msg_bajo in ["si", "sí", "yes", "confirmar", "ok"]:
            items   = sesion.get("items", [])
            resumen = sesion.get("resumen", [])
            ok, resultado = registrar_pedidos_multiples(telefono_limpio, items)
            sesiones[telefono_limpio] = {"paso": "menu"}

            if ok:
                resumen_txt     = "\n".join(resumen)
                respuesta_texto = (
                    f"✅ *¡Pedido registrado con éxito!* 🎉\n\n"
                    f"{resumen_txt}\n\n"
                    f"💰 Total: S/ {float(resultado):.2f}\n\n"
                    "🚚 Tu pedido ya figura en nuestro panel. "
                    "Un administrador coordinará la entrega contigo.\n\n"
                    "Escribe *MENU* para hacer otro pedido."
                )
            else:
                respuesta_texto = (
                    f"⚠️ No se pudo completar: {resultado}\n\n"
                    "Escribe *MENU* para reintentar."
                )

        elif msg_bajo in ["no", "cancelar"]:
            sesiones[telefono_limpio] = {"paso": "menu"}
            respuesta_texto = "❌ Pedido cancelado.\n\n" + menu_principal()

        else:
            resumen     = sesion.get("resumen", [])
            total       = sesion.get("total", 0)
            resumen_txt = "\n".join(resumen)
            respuesta_texto = (
                f"📦 Tu pedido pendiente:\n{resumen_txt}\n"
                f"💰 Total: S/ {total:.2f}\n\n"
                "👉 Responde *SI* para confirmar o *NO* para cancelar."
            )

        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")

    # ── ESPERANDO RETORNO DEL CATÁLOGO WEB ───────────────────
    elif paso == "esperando_carrito_web":
        respuesta_texto = (
            "⏳ Aún no hemos recibido tu selección desde el catálogo.\n\n"
            "Por favor abre el enlace que te enviamos, selecciona "
            "tus productos y presiona *Confirmar Pedido* en la web.\n\n"
            "Escribe *MENU* si deseas cancelar."
        )
        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")

    else:
        sesiones[telefono_limpio] = {"paso": "menu"}
        respuesta_texto = menu_principal()
        msg.body(respuesta_texto)
        guardar_mensaje(telefono_limpio, respuesta_texto, origen="bot")

    return str(response)