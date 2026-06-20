# app/whatsapp_page.py
"""
Página independiente del Panel WhatsApp.
Accesible en: http://57.156.66.168:8000/whatsapp
"""
import asyncio
import os
from datetime import datetime, timezone
import flet as ft
import httpx
import traceback
from sqlalchemy.orm import Session
from database import engine
import models

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN  = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "whatsapp:+14155238886")
BASE_URL           = os.getenv("BASE_URL", "http://localhost:8000")


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


def enviar_mensaje_twilio(telefono: str, mensaje: str) -> bool:
    try:
        url  = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        data = {
            "From": TWILIO_FROM_NUMBER,
            "To":   f"whatsapp:+{telefono}",
            "Body": mensaje,
        }
        r = httpx.post(url, data=data,
                       auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                       timeout=10)
        print(f"[TWILIO] Status: {r.status_code}")
        return r.status_code == 201
    except Exception as e:
        print(f"[TWILIO ERROR] {e}")
        return False


async def whatsapp_main(page: ft.Page):
    page.title      = "Smart-Liquor — Panel WhatsApp"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = "#0b0d0f"
    page.padding    = 0
    page.scroll     = ft.ScrollMode.ADAPTIVE

    print("[WHATSAPP PAGE] Iniciando panel WhatsApp independiente...")

    _telefono_activo = {"tel": None, "nombre": None}

    lista_conv_ui  = ft.Column(spacing=6, scroll=ft.ScrollMode.ADAPTIVE)
    col_chat_ui    = ft.Column(spacing=8, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    inp_respuesta  = ft.TextField(
        hint_text="Escribe tu respuesta al cliente...",
        multiline=True, min_lines=2, max_lines=4,
        border_radius=ft.border_radius.all(10),
        bgcolor="#111416", border_color="#232629", expand=True,
    )
    txt_estado_env = ft.Text("", color="green", size=12)
    header_chat    = ft.Text("Selecciona una conversación",
                             size=15, weight="bold", color="grey")
    badge_modo     = ft.Container(visible=False)
    btn_devolver   = ft.ElevatedButton(
        "Devolver al Bot", icon=ft.icons.SMART_TOY,
        bgcolor="#333", color="white", height=34, visible=False,
    )

    # ── Lista de conversaciones ───────────────────────────────
    async def refrescar_lista():
        print("[WHATSAPP PAGE] Refrescando lista...")
        try:
            mensajes = await run_db(lambda db: (
                db.query(models.MensajeWhatsapp)
                .order_by(models.MensajeWhatsapp.fecha.desc())
                .all()
            ))

            conversaciones = {}
            for m in mensajes:
                if m.telefono not in conversaciones:
                    conversaciones[m.telefono] = []
                conversaciones[m.telefono].append(m)

            lista_conv_ui.controls.clear()

            if not conversaciones:
                lista_conv_ui.controls.append(
                    ft.Text("Sin conversaciones aún.", color="grey",
                            italic=True, size=12)
                )
                await page.update_async()
                return

            for tel, msgs in conversaciones.items():
                cliente = await run_db(lambda db, t=tel: (
                    db.query(models.Cliente)
                    .filter(models.Cliente.telefono == t)
                    .first()
                ))
                nombre          = (cliente.nombre_completo if cliente else tel) or tel
                no_leidos       = sum(1 for m in msgs
                                      if not m.leido and m.origen == "cliente")
                es_activo       = _telefono_activo["tel"] == tel
                requiere_agente = cliente.modo_agente if cliente else False

                ultimo_msg = ""
                if msgs:
                    ult = msgs[0]
                    ultimo_msg = (ult.mensaje[:35] + "...") \
                        if len(ult.mensaje) > 35 else ult.mensaje

                tel_limpio = tel.replace("whatsapp:", "")

                badge_nl = ft.Container(
                    content=ft.Text(str(no_leidos), size=10,
                                    color="white", weight="bold"),
                    bgcolor="red",
                    border_radius=ft.border_radius.all(10),
                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    visible=no_leidos > 0,
                )
                badge_agente = ft.Container(
                    content=ft.Text("AGENTE", size=9,
                                    color="#ff9800", weight="bold"),
                    bgcolor="#2a1a00",
                    border=ft.border.all(1, "#ff9800"),
                    border_radius=ft.border_radius.all(4),
                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    visible=requiere_agente,
                )

                fila = ft.Container(
                    content=ft.Row([
                        ft.Icon(
                            ft.icons.ACCOUNT_CIRCLE,
                            color="#25D366" if requiere_agente else "#2196f3",
                            size=32,
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
                    ], spacing=10, vertical_alignment="center"),
                    bgcolor="#1a1f26" if es_activo else "#111416",
                    border_radius=ft.border_radius.all(10),
                    padding=ft.padding.symmetric(horizontal=12, vertical=10),
                    border=ft.border.all(1, "#2196f3" if es_activo else "#1a1d20"),
                    on_click=lambda e, t=tel, n=nombre: page.run_task(cargar_chat, t, n),
                )
                lista_conv_ui.controls.append(fila)

            print(f"[WHATSAPP PAGE] {len(lista_conv_ui.controls)} conversacion(es) cargadas")
            await asyncio.sleep(0.1)
            await page.update_async()

        except Exception as ex:
            print(f"[WHATSAPP PAGE ERROR] {ex}")
            traceback.print_exc()

    # ── Cargar historial ──────────────────────────────────────
    async def cargar_chat(telefono: str, nombre: str):
        _telefono_activo["tel"]    = telefono
        _telefono_activo["nombre"] = nombre
        header_chat.value = f"💬 {nombre} — {telefono}"
        header_chat.color = "white"

        try:
            mensajes = await run_db(lambda db: (
                db.query(models.MensajeWhatsapp)
                .filter(models.MensajeWhatsapp.telefono == telefono)
                .order_by(models.MensajeWhatsapp.fecha.asc())
                .all()
            ))

            def _marcar_leidos(db):
                db.query(models.MensajeWhatsapp).filter(
                    models.MensajeWhatsapp.telefono == telefono,
                    models.MensajeWhatsapp.leido == False,
                ).update({"leido": True})
                db.commit()

            await run_db(_marcar_leidos)

            cliente = await run_db(lambda db: (
                db.query(models.Cliente)
                .filter(models.Cliente.telefono == telefono)
                .first()
            ))
            en_modo_agente       = cliente.modo_agente if cliente else False
            badge_modo.visible   = en_modo_agente
            btn_devolver.visible = en_modo_agente

            col_chat_ui.controls.clear()

            if not mensajes:
                col_chat_ui.controls.append(
                    ft.Text("Sin mensajes aún.", color="grey", italic=True)
                )
            else:
                for m in mensajes:
                    es_agente   = m.origen == "agente"
                    es_bot      = m.origen == "bot"
                    color_bg    = "#1a2a1a" if es_agente else \
                                  ("#1a1f26" if es_bot else "#16191c")
                    alineacion  = ft.MainAxisAlignment.END if es_agente \
                                  else ft.MainAxisAlignment.START
                    color_label = "#66bb6a" if es_agente else \
                                  ("#2196f3" if es_bot else "#fbbf24")
                    label       = "Tú (agente)" if es_agente else \
                                  ("🤖 Bot" if es_bot else "Cliente")
                    fecha_str   = ""
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
                                        ft.Text(label, size=10,
                                                color=color_label,
                                                weight="bold"),
                                        ft.Text(fecha_str, size=10, color="#555"),
                                    ], spacing=8),
                                    ft.Text(m.mensaje, size=13,
                                            color="white", selectable=True),
                                ], spacing=3),
                                bgcolor=color_bg,
                                border_radius=ft.border_radius.all(10),
                                padding=ft.padding.symmetric(
                                    horizontal=12, vertical=8),
                                max_width=500,
                            )
                        ], alignment=alineacion)
                    )

            await asyncio.sleep(0.1)
            await page.update_async()
            await refrescar_lista()

        except Exception as ex:
            print(f"[CHAT ERROR] {ex}")
            traceback.print_exc()

    # ── Enviar respuesta ──────────────────────────────────────
    async def enviar_respuesta(e):
        telefono = _telefono_activo["tel"]
        mensaje  = inp_respuesta.value.strip()
        if not telefono or not mensaje:
            return
        txt_estado_env.value = "Enviando..."
        txt_estado_env.color = "grey"
        await page.update_async()

        ok = await asyncio.to_thread(enviar_mensaje_twilio, telefono, mensaje)

        if ok:
            def _guardar(db):
                cliente = db.query(models.Cliente).filter(
                    models.Cliente.telefono == telefono
                ).first()
                db.add(models.MensajeWhatsapp(
                    telefono=telefono,
                    cliente_id=cliente.id if cliente else None,
                    mensaje=mensaje,
                    origen="agente",
                    leido=True,
                ))
                if cliente:
                    cliente.ultimo_mensaje = datetime.now(timezone.utc)
                db.commit()

            await run_db(_guardar)
            inp_respuesta.value  = ""
            txt_estado_env.value = "✅ Mensaje enviado"
            txt_estado_env.color = "green"
            await cargar_chat(telefono, _telefono_activo["nombre"])
        else:
            txt_estado_env.value = "❌ Error al enviar. Verifica credenciales Twilio."
            txt_estado_env.color = "red"
        await page.update_async()

    # ── Devolver al bot ───────────────────────────────────────
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
        await asyncio.to_thread(
            enviar_mensaje_twilio, telefono,
            "✅ Has sido reconectado con el bot de Smart-Liquor.\n\n"
            "Escribe *MENU* para ver las opciones disponibles."
        )
        txt_estado_env.value = "✅ Cliente devuelto al bot"
        txt_estado_env.color = "green"
        badge_modo.visible   = False
        btn_devolver.visible = False
        await cargar_chat(telefono, _telefono_activo["nombre"])

    btn_devolver.on_click = devolver_al_bot

    # ── Badge modo agente ─────────────────────────────────────
    badge_modo.content = ft.Container(
        content=ft.Row([
            ft.Icon(ft.icons.PERSON, color="#ff9800", size=14),
            ft.Text("Modo Agente Activo", color="#ff9800",
                    size=12, weight="bold"),
        ], spacing=6),
        bgcolor="#2a1a00",
        border=ft.border.all(1, "#ff9800"),
        border_radius=ft.border_radius.all(6),
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
    )

    # ── Funcion para volver al dashboard ─────────────────────
    async def volver_dashboard(e):
        await page.launch_url_async(BASE_URL)

    # ── Header ────────────────────────────────────────────────
    header = ft.Container(
        padding=ft.padding.symmetric(horizontal=20, vertical=12),
        bgcolor="#0f1214",
        border=ft.Border(bottom=ft.BorderSide(1, "#1a1d20")),
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.CHAT, color="#25D366", size=22),
                ft.Text("Panel WhatsApp", size=18, weight="bold", color="white"),
                ft.Text("Smart-Liquor", size=12, color="grey"),
            ], spacing=10),
            ft.Row([
                ft.IconButton(
                    ft.icons.REFRESH, icon_color="white", icon_size=20,
                    tooltip="Actualizar conversaciones",
                    on_click=lambda e: page.run_task(refrescar_lista),
                ),
                ft.ElevatedButton(
                    "← Volver al Dashboard",
                    bgcolor="#1a1f26", color="white", height=34,
                    on_click=volver_dashboard,
                ),
            ], spacing=8),
        ], alignment="spaceBetween"),
    )

    # ── Layout ────────────────────────────────────────────────
    layout = ft.Row([
        ft.Container(
            width=300,
            bgcolor="#0f1214",
            border=ft.Border(right=ft.BorderSide(1, "#1a1d20")),
            padding=ft.padding.all(12),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.CHAT, color="#25D366", size=18),
                    ft.Text("Conversaciones", size=14, weight="bold",
                            color="white", expand=True),
                    ft.IconButton(
                        ft.icons.REFRESH, icon_color="grey", icon_size=14,
                        on_click=lambda e: page.run_task(refrescar_lista),
                    ),
                ], spacing=8, vertical_alignment="center"),
                ft.Divider(height=8, color="#1a1d20"),
                lista_conv_ui,
            ], spacing=8, expand=True),
        ),
        ft.Container(
            expand=True,
            bgcolor="#0b0d0f",
            padding=ft.padding.all(16),
            content=ft.Column([
                ft.Row([
                    header_chat, badge_modo, btn_devolver,
                ], spacing=12, vertical_alignment="center"),
                ft.Divider(height=6, color="#1a1d20"),
                ft.Container(
                    content=col_chat_ui,
                    expand=True,
                    bgcolor="#0f1214",
                    border_radius=ft.border_radius.all(10),
                    padding=12,
                    height=500,
                ),
                ft.Divider(height=6, color="#1a1d20"),
                ft.Row([
                    inp_respuesta,
                    ft.IconButton(
                        icon=ft.icons.SEND,
                        icon_color="#25D366", icon_size=28,
                        tooltip="Enviar mensaje",
                        on_click=enviar_respuesta,
                        bgcolor="#0f1214",
                    ),
                ], spacing=8, vertical_alignment="end"),
                txt_estado_env,
            ], spacing=8, expand=True),
        ),
    ], expand=True, spacing=0)
    async def on_page_load(e):
        print("[WHATSAPP PAGE] on_resize disparado")
        await asyncio.sleep(0.3)
        await page.update_async()
        await refrescar_lista()

    page.on_resize = on_page_load

    # ── Montar página y cargar ────────────────────────────────
    page.controls.clear()
    page.controls.extend([
        header,
        ft.Container(
            content=layout,
            expand=True,
            height=page.height - 70 if page.height else 700,  # ← altura calculada
        ),
    ])
    await asyncio.sleep(0.1)
    await page.update_async()
    await refrescar_lista()