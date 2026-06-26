# app/componentes/fila_inventario.py
import flet as ft


def build_fila_inventario(pr, abrir_suministro, abrir_eliminar, abrir_editar_producto=None):
    stock_actual = pr.stock_actual or 0
    stock_minimo = pr.stock_minimo or 10
    es_bajo = stock_actual <= stock_minimo
    es_desc = pr.nombre.startswith("[DESCONTINUADO]")

    if es_desc:
        stock_color      = "#555d66"
        badge_bg         = "#232629"
        badge_text       = "DESCONTINUADO"
        badge_text_color = "grey"
    elif stock_actual == 0:
        stock_color      = "#ef5350"
        badge_bg         = "#2c1a1d"
        badge_text       = "SIN STOCK"
        badge_text_color = "#ef5350"
    elif es_bajo:
        stock_color      = "#ffb74d"
        badge_bg         = "#2c241a"
        badge_text       = "STOCK BAJO"
        badge_text_color = "#ffb74d"
    else:
        stock_color      = "#66bb6a"
        badge_bg         = "#1a2c1e"
        badge_text       = "ÓPTIMO"
        badge_text_color = "#66bb6a"

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(
                    ft.icons.LOCAL_DRINK if not es_desc else ft.icons.DO_NOT_DISTURB_ON,
                    color=stock_color if not es_desc else "grey",
                    size=20
                ),
                bgcolor="#111416",
                padding=10,
                border_radius=8,
            ),

            ft.Container(
                content=ft.Column([
                    ft.Text(
                        pr.nombre,
                        weight="bold",
                        size=15,
                        color="#71777f" if es_desc else "white",
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"ID: #{pr.id:03d} • Alerta por debajo de {stock_minimo} uds",
                        color="grey",
                        size=11
                    )
                ], spacing=2, alignment="center"),
                expand=4,
            ),

            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(
                            badge_text,
                            size=10,
                            weight="bold",
                            color=badge_text_color
                        ),
                        bgcolor=badge_bg,
                        border_radius=6,
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border=ft.border.all(1, badge_text_color)
                    ),
                    ft.Text(
                        f"{stock_actual} uds",
                        weight="bold",
                        size=15,
                        color=stock_color
                    )
                ], spacing=12, alignment="center"),
                expand=3,
                alignment=ft.alignment.center_left
            ),

            ft.Container(
                content=ft.Text(
                    f"S/ {pr.precio_venta:.2f}",
                    color="#ffc107" if not es_desc else "grey",
                    weight="w600",
                    size=15,
                ),
                expand=2,
                alignment=ft.alignment.center_right,
                padding=ft.padding.only(right=15)
            ),

            ft.Row([
                ft.IconButton(
                    icon=ft.icons.EDIT,
                    icon_color="#2196f3",
                    icon_size=20,
                    tooltip="Editar producto",
                    visible=abrir_editar_producto is not None,
                    style=ft.ButtonStyle(
                        bgcolor={"": "transparent", "hover": "#1a1f26"},
                        shape=ft.RoundedRectangleBorder(radius=6)
                    ),
                    on_click=lambda e, pid=pr.id: abrir_editar_producto(pid) if abrir_editar_producto else None,
                ),
                ft.IconButton(
                    icon=ft.icons.ADD_BUSINESS,
                    icon_color="#66bb6a",
                    icon_size=20,
                    tooltip="Suministrar / Incrementar stock",
                    visible=not es_desc,
                    style=ft.ButtonStyle(
                        bgcolor={"": "transparent", "hover": "#1a2c1e"},
                        shape=ft.RoundedRectangleBorder(radius=6)
                    ),
                    on_click=lambda e, pid=pr.id: abrir_suministro(pid),
                ),
                ft.IconButton(
                    icon=ft.icons.DELETE_OUTLINE,
                    icon_color="#ef5350",
                    icon_size=20,
                    tooltip="Remover producto del sistema",
                    style=ft.ButtonStyle(
                        bgcolor={"": "transparent", "hover": "#2c1a1d"},
                        shape=ft.RoundedRectangleBorder(radius=6)
                    ),
                    on_click=lambda e, pid=pr.id, nom=pr.nombre: abrir_eliminar(pid, nom),
                ),
            ], spacing=4, alignment="end")

        ], alignment="spaceBetween", vertical_alignment="center"),

        padding=ft.padding.symmetric(horizontal=16, vertical=10),
        bgcolor="#111416",
        border_radius=12,
        border=ft.border.all(1, "#1a1d20"),
        animate=ft.animation.Animation(200, "easeOut"),
    )