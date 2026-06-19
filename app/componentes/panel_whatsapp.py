# app/componentes/panel_whatsapp.py
"""
Panel de atención de WhatsApp para el administrador.
Permite monitorear conversaciones, ver historial y responder
directamente desde el dashboard usando la API de Twilio.
"""
import asyncio
from datetime import datetime, timezone
import flet as ft
import httpx
from sqlalchemy.orm import Session, joinedload
from database import engine
import models

# ── Credenciales Twilio ───────────────────────────────────────
# Estas van en el .env — las leemos con os.getenv
import os
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")


def enviar_mensaje_twilio(telefono: str, mensaje: str) -> bool:
    """Envía un mensaje de WhatsApp usando la API REST de Twilio."""
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        data = {
            "From": TWILIO_FROM_NUMBER,
            "To":   f"whatsapp:+{telefono}",
            "Body": mensaje,
        }
        response = httpx.post(
            url, data=data,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=10,
        )
        return response.status_code == 201
    except Exception as e:
        print(f"[TWILIO ERROR] {e}")
        return False


def guardar_mensaje_agente(telefono: str, mensaje: str):
    """Guarda el mensaje del agente en el historial."""
    try:
        with Session(engine) as db:
            cliente = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            nuevo = models.MensajeWhatsapp(
                telefono=telefono,
                cliente_id=cliente.id if cliente else None,
                mensaje=mensaje,
                origen="agente",
            )
            db.add(nuevo)
            if cliente:
                cliente.ultimo_mensaje = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        print(f"[ERROR guardar_mensaje_agente] {e}")


def desactivar_modo_agente(telefono: str):
    """Devuelve el control al bot."""
    try:
        with Session(engine) as db:
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if c:
                c.modo_agente = False
                db.commit()
    except Exception as e:
        print(f"[ERROR desactivar_modo_agente] {e}")


def build_panel_whatsapp(page: ft.Page, run_db):
    """
    Construye el panel de WhatsApp para el administrador.
    Retorna (panel, refrescar_panel)
    """
    # ── Estado interno ────────────────────────────────────────
    _conversaciones    = []
    _telefono_activo   = {"tel": None, "nombre": None}

    # ── Componentes UI ────────────────────────────────────────
    lista_conv_ui  = ft.Column(spacing=6, scroll=ft.ScrollMode.ADAPTIVE)
    col_chat_ui    = ft.Column(spacing=8, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    txt_sin_chat   = ft.Text(
        "Selecciona una conversación para ver el historial",
        color="grey", italic=True, size=13
    )
    inp_respuesta  = ft.TextField(
        hint_text="Escribe tu respuesta al cliente...",
        multiline=True, min_lines=2, max_lines=4,
        border_radius=10, bgcolor="#111416",
        border_color="#232629", expand=True,
    )
    txt_estado_env = ft.Text("", color="green", size=12)
    header_chat    = ft.Text("", size=16, weight="bold", color="white")
    badge_modo     = ft.Container(visible=False)
    btn_devolver   = ft.ElevatedButton(
        "Devolver al Bot",
        icon=ft.icons.SMART_TOY,
        bgcolor="#333",
        color="white",
        height=34,
        visible=False,
    )

    # ── Cargar historial de una conversacion ──────────────────
    async def cargar_chat(telefono: str, nombre: str):
        _telefono_activo["tel"]    = telefono
        _telefono_activo["nombre"] = nombre
        header_chat.value = f"💬 {nombre} — {telefono}"

        try:
            mensajes = await run_db(lambda db: (
                db.query(models.MensajeWhatsapp)
                .filter(models.MensajeWhatsapp.telefono == telefono)
                .order_by(models.MensajeWhatsapp.fecha.asc())
                .all()
            ))

            # Marcar como leidos
            await run_db(lambda db: (
                db.query(models.MensajeWhatsapp)
                .filter(
                    models.MensajeWhatsapp.telefono == telefono,
                    models.MensajeWhatsapp.leido == False,
                )
                .update({"leido": True})
            ))

            # Verificar si está en modo agente
            cliente = await run_db(lambda db: (
                db.query(models.Cliente)
                .filter(models.Cliente.telefono == telefono)
                .first()
            ))
            en_modo_agente = cliente.modo_agente if cliente else False

            badge_modo.visible = en_modo_agente
            btn_devolver.visible = en_modo_agente

            col_chat_ui.controls.clear()

            if not mensajes:
                col_chat_ui.controls.append(
                    ft.Text("Sin mensajes aún.", color="grey", italic=True)
                )
            else:
                for m in mensajes:
                    es_cliente = m.origen == "cliente"
                    es_bot     = m.origen == "bot"
                    es_agente  = m.origen == "agente"

                    color_bg   = "#1a2a1a" if es_agente else ("#1a1f26" if es_bot else "#16191c")
                    alineacion = ft.MainAxisAlignment.END if (es_agente) else ft.MainAxisAlignment.START
                    color_txt  = "#66bb6a" if es_agente else ("#2196f3" if es_bot else "white")
                    label      = "Tú (agente)" if es_agente else ("🤖 Bot" if es_bot else "Cliente")

                    fecha_str = ""
                    if m.fecha:
                        try:
                            fecha_str = m.fecha.strftime("%d/%m %H:%M")
                        except Exception:
                            fecha_str = ""

                    col_chat_ui.controls.append(
                        ft.Row([
                            ft.Container(
                                content=ft.Column([
                                    ft.Row([
                                        ft.Text(label, size=10, color=color_txt, weight="bold"),
                                        ft.Text(fecha_str, size=10, color="#555"),
                                    ], spacing=8),
                                    ft.Text(m.mensaje, size=13, color="white",
                                            selectable=True),
                                ], spacing=3),
                                bgcolor=color_bg,
                                border_radius=10,
                                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                                max_width=380,
                            )
                        ], alignment=alineacion)
                    )

            await page.update_async()
            await refrescar_lista()

        except Exception as ex:
            print(f"[CHAT ERROR] {ex}")

    # ── Enviar respuesta al cliente ───────────────────────────
    async def enviar_respuesta(e):
        telefono = _telefono_activo["tel"]
        mensaje  = inp_respuesta.value.strip()

        if not telefono or not mensaje:
            return

        txt_estado_env.value = "Enviando..."
        txt_estado_env.color = "grey"
        await page.update_async()

        # Enviar via Twilio en hilo separado
        def _enviar():
            return enviar_mensaje_twilio(telefono, mensaje)

        ok = await asyncio.to_thread(_enviar)

        if ok:
            # Guardar en historial
            def _guardar(db):
                cliente = db.query(models.Cliente).filter(
                    models.Cliente.telefono == telefono
                ).first()
                nuevo = models.MensajeWhatsapp(
                    telefono=telefono,
                    cliente_id=cliente.id if cliente else None,
                    mensaje=mensaje,
                    origen="agente",
                    leido=True,
                )
                db.add(nuevo)
                if cliente:
                    cliente.ultimo_mensaje = datetime.now(timezone.utc)
                db.commit()

            await run_db(_guardar)
            inp_respuesta.value = ""
            txt_estado_env.value = "✅ Mensaje enviado"
            txt_estado_env.color = "green"
            await cargar_chat(telefono, _telefono_activo["nombre"])
        else:
            txt_estado_env.value = "❌ Error al enviar. Verifica credenciales Twilio."
            txt_estado_env.color = "red"

        await page.update_async()

    # ── Devolver control al bot ───────────────────────────────
    async def devolver_al_bot(e):
        telefono = _telefono_activo["tel"]
        if not telefono:
            return

        def _desactivar(db):
            c = db.query(models.Cliente).filter(
                models.Cliente.telefono == telefono
            ).first()
            if c:
                c.modo_agente = False
                db.commit()

        await run_db(_desactivar)

        # Notificar al cliente
        def _notificar():
            enviar_mensaje_twilio(
                telefono,
                "✅ Has sido reconectado con el bot de Smart-Liquor.\n\n"
                "Escribe *MENU* para ver las opciones disponibles."
            )

        await asyncio.to_thread(_notificar)

        txt_estado_env.value = "✅ Cliente devuelto al bot"
        txt_estado_env.color = "green"
        badge_modo.visible   = False
        btn_devolver.visible = False
        await cargar_chat(telefono, _telefono_activo["nombre"])

    btn_devolver.on_click = devolver_al_bot

    # ── Construir lista de conversaciones ─────────────────────
    async def refrescar_lista():
        try:
            clientes = await run_db(lambda db: (
                db.query(models.Cliente)
                .join(models.MensajeWhatsapp,
                      models.Cliente.telefono == models.MensajeWhatsapp.telefono)
                .options(joinedload(models.Cliente.mensajes))
                .order_by(models.Cliente.ultimo_mensaje.desc().nullslast())
                .distinct()
                .all()
            ))

            lista_conv_ui.controls.clear()

            if not clientes:
                lista_conv_ui.controls.append(
                    ft.Text("Sin conversaciones aún.", color="grey",
                            italic=True, size=12)
                )
                await page.update_async()
                return

            for c in clientes:
                tel      = c.telefono
                nombre   = c.nombre_completo or tel
                no_leidos = sum(
                    1 for m in c.mensajes
                    if not m.leido and m.origen == "cliente"
                )
                es_activo    = _telefono_activo["tel"] == tel
                requiere_agente = c.modo_agente

                # Badge de no leídos
                badge_nl = ft.Container(
                    content=ft.Text(str(no_leidos), size=10,
                                    color="white", weight="bold"),
                    bgcolor="red", border_radius=10,
                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    visible=no_leidos > 0,
                )

                # Badge modo agente
                badge_agente = ft.Container(
                    content=ft.Text("AGENTE", size=9,
                                    color="#ff9800", weight="bold"),
                    bgcolor="#2a1a00",
                    border=ft.border.all(1, "#ff9800"),
                    border_radius=4,
                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    visible=requiere_agente,
                )

                ultimo_msg = ""
                if c.mensajes:
                    msgs_ord = sorted(c.mensajes, key=lambda m: m.fecha or datetime.min)
                    if msgs_ord:
                        ult = msgs_ord[-1]
                        ultimo_msg = (ult.mensaje[:35] + "...") if len(ult.mensaje) > 35 else ult.mensaje

                tel_limpio = tel.replace("whatsapp:", "")

                fila = ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(
                                ft.icons.ACCOUNT_CIRCLE,
                                color="#25D366" if requiere_agente else "#2196f3",
                                size=32,
                            ),
                            padding=4,
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Text(nombre, size=13, weight="bold",
                                        color="white", expand=True,
                                        overflow=ft.TextOverflow.ELLIPSIS),
                                badge_agente,
                                badge_nl,
                            ], spacing=6),
                            ft.Text(tel_limpio, size=10, color="grey"),
                            ft.Text(ultimo_msg, size=11, color="#555",
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ], expand=True, spacing=2),
                    ], spacing=8, vertical_alignment="center"),
                    bgcolor="#1a1f26" if es_activo else "#111416",
                    border_radius=10,
                    padding=ft.padding.symmetric(horizontal=12, vertical=8),
                    border=ft.border.all(1, "#2196f3" if es_activo else "#1a1d20"),
                    on_click=lambda e, t=tel, n=nombre: asyncio.ensure_future(
                        cargar_chat(t, n)
                    ),
                )
                lista_conv_ui.controls.append(fila)

            await page.update_async()
        except Exception as ex:
            print(f"[LISTA CONV ERROR] {ex}")

    async def refrescar_panel():
        await refrescar_lista()
        # Si hay chat activo, recargar mensajes nuevos
        if _telefono_activo["tel"]:
            await cargar_chat(
                _telefono_activo["tel"],
                _telefono_activo["nombre"]
            )

    # ── Badge modo agente ─────────────────────────────────────
    badge_modo.content = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.PERSON, color="#ff9800", size=14),
            ft.Text("Modo Agente Activo", color="#ff9800",
                    size=12, weight="bold"),
        ], spacing=6),
        bgcolor="#2a1a00",
        border=ft.border.all(1, "#ff9800"),
        border_radius=6,
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
    )

    # ── Layout del panel ──────────────────────────────────────
    panel = ft.Row([

        # Columna izquierda — lista de conversaciones
        ft.Container(
            width=280,
            bgcolor="#0f1214",
            border=ft.Border(right=ft.BorderSide(1, "#1a1d20")),
            padding=ft.padding.all(12),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.CHAT, color="#25D366", size=20),
                    ft.Text("Conversaciones", size=16,
                            weight="bold", color="white", expand=True),
                    ft.IconButton(
                        ft.icons.REFRESH,
                        icon_color="grey", icon_size=16,
                        tooltip="Actualizar",
                        on_click=lambda e: asyncio.ensure_future(refrescar_lista()),
                    ),
                ], spacing=8, vertical_alignment="center"),
                ft.Divider(height=10, color="#1a1d20"),
                ft.Container(
                    content=lista_conv_ui,
                    expand=True,
                    height=600,
                ),
            ], spacing=8),
        ),

        # Columna derecha — chat activo
        ft.Container(
            expand=True,
            bgcolor="#0b0d0f",
            padding=ft.padding.all(16),
            content=ft.Column([

                # Header del chat
                ft.Row([
                    header_chat,
                    badge_modo,
                    btn_devolver,
                ], spacing=12, vertical_alignment="center"),

                ft.Divider(height=8, color="#1a1d20"),

                # Mensajes
                ft.Container(
                    content=col_chat_ui,
                    expand=True,
                    height=480,
                    bgcolor="#0f1214",
                    border_radius=10,
                    padding=12,
                ),

                ft.Divider(height=8, color="#1a1d20"),

                # Input de respuesta
                ft.Row([
                    inp_respuesta,
                    ft.IconButton(
                        icon=ft.icons.SEND,
                        icon_color="#25D366",
                        icon_size=28,
                        tooltip="Enviar mensaje",
                        on_click=enviar_respuesta,
                        bgcolor="#0f1214",
                    ),
                ], spacing=8, vertical_alignment="end"),

                txt_estado_env,

            ], spacing=8, expand=True),
        ),

    ], expand=True, spacing=0)

    return panel, refrescar_panel