# app/componentes/panel_clientes.py
import asyncio
from datetime import datetime
import flet as ft


def build_panel_clientes(page: ft.Page, run_db, models, crud):
    lista_clientes_ui  = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    txt_total_clientes = ft.Container(
        content=ft.Text("0 registrados", size=11, color="#2196f3", weight="bold"),
        bgcolor="#1a1f26",
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
        border_radius=6
    )
    _todos_los_clientes = []

    inp_busqueda = ft.TextField(
        hint_text="Buscar cliente por nombre, apellidos o número telefónico...",
        border_radius=12, height=46, text_size=14, content_padding=12,
        prefix_icon=ft.icons.SEARCH,
        bgcolor="#111416", border_color="#232629", focused_border_color="#2196f3",
    )

    def filtrar_clientes(termino: str):
        if not termino.strip():
            return _todos_los_clientes
        t = termino.lower()
        return [
            c for c in _todos_los_clientes
            if t in (c.nombre_completo or "").lower()
            or t in (c.telefono or "").lower()
        ]

    async def on_busqueda(e):
        clientes_filtrados = filtrar_clientes(e.control.value)
        await construir_lista(clientes_filtrados)
        await page.update_async()

    inp_busqueda.on_change = on_busqueda

    async def construir_lista(clientes):
        lista_clientes_ui.controls.clear()
        txt_total_clientes.content.value = f"{len(clientes)} cliente{'s' if len(clientes) != 1 else ''}"

        if not clientes:
            lista_clientes_ui.controls.append(
                ft.Container(
                    content=ft.Text(
                        "No se encontraron clientes registrados.",
                        color="grey", italic=True, size=13
                    ),
                    padding=20,
                )
            )
            return

        for c in clientes:
            total_pedidos = len(c.pedidos) if c.pedidos else 0
            total_gastado = sum(
                p.total_pedido for p in c.pedidos if p.total_pedido
            ) if c.pedidos else 0.0

            # Fecha del último pedido
            fecha_ultimo = ""
            if c.pedidos:
                pedidos_con_fecha = [p for p in c.pedidos if p.fecha_hora]
                if pedidos_con_fecha:
                    ultimo = max(pedidos_con_fecha, key=lambda p: p.fecha_hora)
                    fh = (ultimo.fecha_hora if isinstance(ultimo.fecha_hora, datetime)
                          else datetime.fromisoformat(str(ultimo.fecha_hora)))
                    fecha_ultimo = fh.strftime("%d/%m/%Y")

            # Fecha del primer pedido
            fecha_primero = ""
            if c.pedidos:
                pedidos_con_fecha = [p for p in c.pedidos if p.fecha_hora]
                if pedidos_con_fecha:
                    primero = min(pedidos_con_fecha, key=lambda p: p.fecha_hora)
                    fh = (primero.fecha_hora if isinstance(primero.fecha_hora, datetime)
                          else datetime.fromisoformat(str(primero.fecha_hora)))
                    fecha_primero = fh.strftime("%d/%m/%Y")

            es_whatsapp  = (c.telefono or "").startswith("whatsapp:")
            tel_limpio   = (c.telefono or "").replace("whatsapp:", "")
            fuente_icon  = ft.icons.PHONELINK_RING if es_whatsapp else ft.icons.ASSIGNMENT_IND
            fuente_color = "#25D366" if es_whatsapp else "#2196f3"
            fuente_label = "WHATSAPP" if es_whatsapp else "MANUAL"

            # Historial de fechas de pedidos (desplegable)
            fechas_pedidos = []
            if c.pedidos:
                pedidos_ordenados = sorted(
                    [p for p in c.pedidos if p.fecha_hora],
                    key=lambda p: p.fecha_hora, reverse=True
                )
                for p in pedidos_ordenados[:5]:  # Últimos 5
                    fh = (p.fecha_hora if isinstance(p.fecha_hora, datetime)
                          else datetime.fromisoformat(str(p.fecha_hora)))
                    fechas_pedidos.append(
                        ft.Row([
                            ft.Icon(ft.icons.RECEIPT, size=11, color="#2196f3"),
                            ft.Text(f"Pedido #{p.id:04d}", size=11, color="grey"),
                            ft.Text(fh.strftime("%d/%m/%Y %H:%M"), size=11, color="#ffc107"),
                            ft.Text(f"S/ {p.total_pedido:.2f}" if p.total_pedido else "", 
                                   size=11, color="#66bb6a"),
                        ], spacing=8)
                    )

            panel_fechas = ft.Container(
                visible=False,
                content=ft.Column([
                    ft.Divider(height=8, color="#1a1d20"),
                    ft.Text("HISTORIAL DE PEDIDOS", size=10, color="grey", weight="bold"),
                    ft.Column(fechas_pedidos if fechas_pedidos else [
                        ft.Text("Sin pedidos registrados", size=11, color="grey", italic=True)
                    ], spacing=4),
                ], spacing=6),
                padding=ft.padding.only(left=16, right=16, bottom=8, top=4),
            )

            btn_historial = ft.IconButton(
                icon=ft.icons.HISTORY,
                icon_color="grey",
                icon_size=18,
                tooltip="Ver historial de pedidos",
            )

            async def toggle_historial(e, panel=panel_fechas, btn=btn_historial):
                panel.visible = not panel.visible
                btn.icon_color = "#ffc107" if panel.visible else "grey"
                await page.update_async()

            btn_historial.on_click = toggle_historial

            lista_clientes_ui.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(fuente_icon, color=fuente_color, size=20),
                                bgcolor=f"{fuente_color}10",
                                padding=12, border_radius=50,
                                alignment=ft.alignment.center
                            ),

                            ft.Container(
                                content=ft.Column([
                                    ft.Text(
                                        c.nombre_completo or "Cliente Sin Nombre",
                                        weight="bold", size=15, color="white",
                                        overflow=ft.TextOverflow.ELLIPSIS
                                    ),
                                    ft.Row([
                                        ft.Text(f"📞 {tel_limpio}", color="grey", size=12),
                                        ft.Container(
                                            content=ft.Text(fuente_label, size=9,
                                                           color=fuente_color, weight="bold"),
                                            bgcolor=f"{fuente_color}15",
                                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                            border=ft.border.all(1, fuente_color)
                                        )
                                    ], spacing=8)
                                ], spacing=4, alignment="center"),
                                expand=3,
                            ),

                            ft.Container(
                                content=ft.Column([
                                    ft.Text("DIRECCIÓN DE ENTREGA", size=10, color="grey", weight="bold"),
                                    ft.Text(
                                        c.direccion_exacta or "Dirección no especificada",
                                        size=13, color="white" if c.direccion_exacta else "grey",
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        italic=not c.direccion_exacta
                                    ),
                                    ft.Text(
                                        f"📍 Ref: {c.referencia_ubicacion}",
                                        size=11, color="#ffb74d",
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        visible=bool(c.referencia_ubicacion)
                                    )
                                ], spacing=2, alignment="center"),
                                expand=3,
                            ),

                            ft.Container(
                                content=ft.Column([
                                    ft.Row([
                                        ft.Column([
                                            ft.Text("ÓRDENES", size=10, color="grey", weight="bold"),
                                            ft.Text(f"{total_pedidos} peds", size=13,
                                                   color="#ffc107", weight="bold")
                                        ], spacing=2, alignment="center"),
                                        ft.VerticalDivider(width=20, color="#1a1d20"),
                                        ft.Column([
                                            ft.Text("TOTAL GASTADO", size=10, color="grey", weight="bold"),
                                            ft.Text(f"S/ {total_gastado:.2f}", size=14,
                                                   color="#66bb6a", weight="bold")
                                        ], spacing=2, alignment="center"),
                                    ], spacing=0),
                                    # Fechas primer y último pedido
                                    ft.Row([
                                        ft.Text(
                                            f"🗓 Primero: {fecha_primero}" if fecha_primero else "",
                                            size=10, color="grey"
                                        ),
                                        ft.Text(
                                            f"🕐 Último: {fecha_ultimo}" if fecha_ultimo else "",
                                            size=10, color="#2196f3"
                                        ),
                                    ], spacing=10),
                                ], spacing=4),
                                expand=3,
                                alignment=ft.alignment.center_right
                            ),

                            btn_historial,

                        ], alignment="spaceBetween", vertical_alignment="center"),
                        panel_fechas,
                    ], spacing=0),

                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    bgcolor="#111416",
                    border_radius=12,
                    border=ft.border.all(1, "#1a1d20"),
                )
            )

    async def refrescar_clientes():
        nonlocal _todos_los_clientes
        try:
            from sqlalchemy.orm import joinedload
            clientes = await run_db(lambda db: (
                db.query(models.Cliente)
                .options(joinedload(models.Cliente.pedidos))
                .order_by(models.Cliente.id.desc())
                .all()
            ))
            _todos_los_clientes = clientes
            termino = inp_busqueda.value or ""
            await construir_lista(filtrar_clientes(termino))
            await page.update_async()
        except Exception as ex:
            print(f"[CLIENTES ERROR] {ex}")

    panel = ft.Column([
        ft.Row([
            ft.Row([
                ft.Icon(ft.icons.SUPERVISED_USER_CIRCLE, color="#2196f3", size=22),
                ft.Text("Directorio de Clientes", size=18, weight="bold", color="white"),
            ], spacing=10),
            ft.Row([
                txt_total_clientes,
                ft.IconButton(
                    ft.icons.REFRESH,
                    icon_color="white", bgcolor="#111416", icon_size=16,
                    tooltip="Actualizar base de datos",
                    on_click=lambda e: page.run_task(refrescar_clientes),
                ),
            ], spacing=8),
        ], alignment="spaceBetween", vertical_alignment="center"),
        ft.Container(content=inp_busqueda, padding=ft.padding.only(top=5, bottom=5)),
        ft.Container(content=lista_clientes_ui, expand=True),
    ], spacing=10, expand=True)

    return panel, refrescar_clientes