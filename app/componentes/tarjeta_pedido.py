# app/componentes/tarjeta_pedido.py
import asyncio
from datetime import datetime
import flet as ft
from constants import ESTADOS_LOGISTICOS


def build_tarjeta_pedido(p, cambiar_estado, cargar_modal_editar, page):
    nombre_cliente = p.cliente.nombre_completo if p.cliente else "Anónimo"
    telefono_cli   = p.cliente.telefono if p.cliente and p.cliente.telefono else "Sin telf."
    total          = p.total_pedido or 0.0
    estado_actual  = p.estado_logistico or "recibido"
    datos_estado   = ESTADOS_LOGISTICOS.get(estado_actual, {"color": "grey", "label": "Desconocido"})
    color_estado   = datos_estado["color"]

    fecha_str = ""
    if p.fecha_hora:
        fh = (p.fecha_hora if isinstance(p.fecha_hora, datetime)
              else datetime.fromisoformat(str(p.fecha_hora)))
        fecha_str = fh.strftime("%d/%m/%Y %H:%M")

    filas_items = []
    if p.items:
        for item in p.items:
            nombre_prod = item.producto.nombre if item.producto else "Producto Eliminado"
            precio_unit = (item.producto.precio_venta or 0) if item.producto else 0
            subtotal    = precio_unit * (item.cantidad or 0)
            filas_items.append(
                ft.Row(controls=[
                    ft.Icon(ft.icons.LOCAL_BAR, size=12, color="#2196f3"),
                    ft.Text(nombre_prod, expand=True, size=13, color="white"),
                    ft.Text(f"x{item.cantidad}", width=50, size=13, color="grey", text_align="right"),
                    ft.Text(f"S/ {subtotal:.2f}", width=90, size=13, color="#ffc107", text_align="right", weight="bold"),
                ], spacing=10, vertical_alignment="center")
            )
    else:
        filas_items.append(
            ft.Text("Sin licores o ítems registrados en la orden", color="grey", size=12, italic=True)
        )

    panel_detalle = ft.Container(
        visible=False,
        content=ft.Column(controls=[
            ft.Divider(height=16, color="#1a1d20"),
            ft.Row(controls=[
                ft.Text("DESCRIPCIÓN DEL LICOR", size=11, color="grey", expand=True, weight="bold"),
                ft.Text("CANT.",    size=11, color="grey", width=50, text_align="right", weight="bold"),
                ft.Text("SUBTOTAL", size=11, color="grey", width=90, text_align="right", weight="bold"),
            ], spacing=10),
            ft.Column(controls=filas_items, spacing=6)
        ], spacing=4),
        padding=ft.padding.only(left=44, right=10, bottom=6),
    )

    btn_expand = ft.IconButton(
        icon=ft.icons.KEYBOARD_ARROW_DOWN,
        icon_color="grey",
        icon_size=20,
        tooltip="Ver desglose de botellas",
    )

    async def toggle(e):
        panel_detalle.visible = not panel_detalle.visible
        btn_expand.icon = ft.icons.KEYBOARD_ARROW_UP if panel_detalle.visible else ft.icons.KEYBOARD_ARROW_DOWN
        btn_expand.icon_color = "#2196f3" if panel_detalle.visible else "grey"
        await page.update_async()

    btn_expand.on_click = toggle

    container_badge = ft.Container(
        content=ft.Text(
            datos_estado["label"].upper(),
            size=11, weight="bold", color=color_estado
        ),
        bgcolor=f"{color_estado}15",
        border=ft.border.all(1, color_estado),
        border_radius=6,
        padding=ft.padding.symmetric(horizontal=10, vertical=6),
    )

    async def _cambiar_estado_popup(e, clave_nuevo_estado):
        datos_nuevo = ESTADOS_LOGISTICOS.get(clave_nuevo_estado, {"color": "grey", "label": "Desconocido"})
        container_badge.content.value = datos_nuevo["label"].upper()
        container_badge.content.color = datos_nuevo["color"]
        container_badge.bgcolor = f"{datos_nuevo['color']}15"
        container_badge.border = ft.border.all(1, datos_nuevo["color"])
        await page.update_async()
        await cambiar_estado(p.id, clave_nuevo_estado)

    menu_estados = ft.PopupMenuButton(
        content=container_badge,
        items=[
            ft.PopupMenuItem(
                text=datos["label"],
                data=clave,
                on_click=lambda e: page.run_task(_cambiar_estado_popup, e, e.control.data)
            ) for clave, datos in ESTADOS_LOGISTICOS.items()
        ],
        tooltip="Cambiar estado logístico"
    )

    return ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.icons.LOCAL_SHIPPING, color="#2196f3", size=18),
                        bgcolor="#1a1f26",
                        padding=10,
                        border_radius=8,
                    ),
                    ft.Column([
                        ft.Text(f"Pedido #{p.id:04d}", weight="bold", size=15, color="white"),
                        ft.Text(fecha_str, color="grey", size=11),
                    ], spacing=2)
                ], spacing=12, expand=2),

                ft.Container(
                    content=ft.Column([
                        ft.Text(nombre_cliente, weight="w600", size=14, color="white", overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"📞 {telefono_cli}", color="grey", size=11),
                    ], spacing=2, alignment="center"),
                    expand=3,
                ),

                ft.Container(
                    content=menu_estados,
                    expand=2,
                    alignment=ft.alignment.center_left
                ),

                ft.Container(
                    content=ft.Text(
                        f"S/ {total:.2f}",
                        color="#ffc107",
                        weight="bold",
                        size=16,
                    ),
                    expand=2,
                    alignment=ft.alignment.center_right,
                    padding=ft.padding.only(right=10)
                ),

                ft.Row([
                    ft.IconButton(
                        icon=ft.icons.EDIT_NOTE,
                        icon_color="#2196f3",
                        icon_size=20,
                        tooltip="Modificar detalles del pedido",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)),
                        on_click=lambda e: page.run_task(cargar_modal_editar, p.id),
                    ),
                    btn_expand,
                ], spacing=4, alignment="end")

            ], vertical_alignment="center", spacing=10),
            panel_detalle,
        ], spacing=0),

        padding=ft.padding.symmetric(horizontal=16, vertical=12),
        bgcolor="#111416",
        border_radius=12,
        border=ft.border.all(1, "#1a1d20"),
        animate=ft.animation.Animation(150, "easeOut"),
    )