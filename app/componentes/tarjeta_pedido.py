# app/componentes/tarjeta_pedido.py
import asyncio
from datetime import datetime
import flet as ft
from constants import ESTADOS_LOGISTICOS


def build_tarjeta_pedido(p, cambiar_estado, cargar_modal_editar, page):
    """
    Construye la tarjeta visual de un pedido con panel expandible.

    Parametros:
        p                  -- objeto Pedido de SQLAlchemy
        cambiar_estado     -- funcion async para cambiar estado logistico
        cargar_modal_editar -- funcion async para abrir el modal de edicion
        page               -- objeto Page de Flet

    Retorna ft.Container con la tarjeta completa.
    """
    nombre_cliente = p.cliente.nombre_completo if p.cliente else "Anonimo"
    total          = p.total_pedido or 0.0
    estado_actual  = p.estado_logistico or "recibido"
    datos_estado   = ESTADOS_LOGISTICOS.get(estado_actual, {"color": "grey", "label": "Desconocido"})
    color_estado   = datos_estado["color"]

    # ── Fecha formateada ──────────────────────────────────────
    fecha_str = ""
    if p.fecha_hora:
        fh = (p.fecha_hora if isinstance(p.fecha_hora, datetime)
              else datetime.fromisoformat(str(p.fecha_hora)))
        fecha_str = fh.strftime("%d/%m/%Y %H:%M")

    # ── Filas de items ────────────────────────────────────────
    filas_items = []
    if p.items:
        for item in p.items:
            nombre_prod = item.producto.nombre if item.producto else "Eliminado"
            precio_unit = (item.producto.precio_venta or 0) if item.producto else 0
            subtotal    = precio_unit * (item.cantidad or 0)
            filas_items.append(
                ft.Row(controls=[
                    ft.Icon("circle", size=7, color="amber"),
                    ft.Text(nombre_prod, expand=True, size=13),
                    ft.Text(
                        f"x{item.cantidad}", width=40, size=13,
                        color="grey", text_align="right"
                    ),
                    ft.Text(
                        f"S/ {subtotal:.2f}", width=75, size=13,
                        color="amber", text_align="right"
                    ),
                ], spacing=8, vertical_alignment="center")
            )
    else:
        filas_items.append(
            ft.Text("Sin items registrados", color="grey", size=12, italic=True)
        )

    # ── Panel colapsable ──────────────────────────────────────
    panel_detalle = ft.Container(
        visible=False,
        content=ft.Column(controls=[
            ft.Divider(height=10, color="#2a2d30"),
            ft.Row(controls=[
                ft.Text("PRODUCTO", size=11, color="#555", expand=True),
                ft.Text("CANT.",    size=11, color="#555", width=40, text_align="right"),
                ft.Text("SUBTOTAL", size=11, color="#555", width=75, text_align="right"),
            ], spacing=8),
            *filas_items,
        ], spacing=6),
        padding=ft.padding.only(left=4, right=4, top=0, bottom=6),
    )

    # ── Boton expandir ────────────────────────────────────────
    btn_expand = ft.IconButton(
        icon="keyboard_arrow_down",
        icon_color="white",
        icon_size=22,
        tooltip="Ver detalle del pedido",
    )

    async def toggle(e, _panel=panel_detalle, _btn=btn_expand):
        _panel.visible  = not _panel.visible
        _btn.icon       = "keyboard_arrow_up" if _panel.visible else "keyboard_arrow_down"
        _btn.icon_color = "amber"             if _panel.visible else "white"
        await page.update_async()

    btn_expand.on_click = toggle

    # ── Dropdown de estado ────────────────────────────────────
    opciones_dropdown = [
        ft.dropdown.Option(key=clave, text=datos["label"])
        for clave, datos in ESTADOS_LOGISTICOS.items()
    ]

    dropdown_estado = ft.Dropdown(
        value=estado_actual,
        width=140,
        content_padding=ft.padding.symmetric(horizontal=10, vertical=4),
        options=opciones_dropdown,
        border_color=color_estado,
        color="white",
        bgcolor="#0b0d0f",
    )

    async def _on_estado_change(e, pid: int, _dd=dropdown_estado):
        nuevo       = e.control.value
        nuevo_color = ESTADOS_LOGISTICOS.get(nuevo, {"color": "grey"})["color"]
        _dd.border_color = nuevo_color
        await page.update_async()
        await cambiar_estado(pid, nuevo)

    dropdown_estado.on_change = lambda e, pid=p.id, _dd=dropdown_estado: (
        asyncio.ensure_future(_on_estado_change(e, pid, _dd))
    )

    # ── Tarjeta completa ──────────────────────────────────────
    return ft.Container(
        content=ft.Column(controls=[
            ft.Row(controls=[
                ft.Icon("shopping_cart", color="orange", size=20),
                ft.Column(controls=[
                    ft.Row([
                        ft.Text(
                            f"Pedido #{p.id}  —  {nombre_cliente}",
                            weight="bold", size=14
                        ),
                        ft.Text(fecha_str, color="#555", size=11),
                    ], spacing=10),
                    ft.Row(controls=[
                        ft.Text(f"S/ {total:.2f}", color="amber", size=13),
                        dropdown_estado,
                    ], spacing=10, vertical_alignment="center"),
                ], expand=True, spacing=4),
                ft.IconButton(
                    icon="edit_note",
                    icon_color="#1565c0",
                    icon_size=22,
                    tooltip="Editar pedido",
                    on_click=lambda e, pid=p.id: asyncio.ensure_future(
                        cargar_modal_editar(pid)
                    ),
                ),
                btn_expand,
            ], vertical_alignment="center", spacing=12),
            panel_detalle,
        ], spacing=0),
        bgcolor="#16191c",
        border_radius=10,
        padding=ft.padding.symmetric(horizontal=14, vertical=10),
    )