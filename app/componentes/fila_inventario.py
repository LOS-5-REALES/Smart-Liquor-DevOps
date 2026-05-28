# app/componentes/fila_inventario.py
import asyncio
import flet as ft


def build_fila_inventario(pr, abrir_suministro, abrir_eliminar):
    """
    Construye la fila visual de un producto en el inventario.

    Parametros:
        pr              -- objeto Producto de SQLAlchemy
        abrir_suministro -- funcion async para abrir modal de stock
        abrir_eliminar   -- funcion async para abrir modal de eliminacion

    Retorna ft.Container con la fila completa.
    """
    es_bajo = (pr.stock_actual or 0) <= (pr.stock_minimo or 10)
    es_desc = pr.nombre.startswith("[DESCONTINUADO]")

    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(
                    pr.nombre,
                    weight="bold",
                    color="#666" if es_desc else "white"
                ),
                ft.Row([
                    ft.Text("Stock disponible:", color="#aaa", size=12),
                    ft.Text(
                        f"{pr.stock_actual}",
                        color="red" if es_bajo else "green",
                        weight="bold",
                        size=15,
                    ),
                    ft.Container(
                        visible=es_bajo and not es_desc,
                        content=ft.Text(
                            "STOCK BAJO", size=9, weight="bold", color="white"
                        ),
                        bgcolor="red",
                        border_radius=4,
                        padding=3,
                    ),
                ], spacing=8),
            ], expand=True, spacing=2),
            ft.IconButton(
                icon="add_circle",
                icon_color="green",
                icon_size=22,
                tooltip="Sumar stock",
                visible=not es_desc,
                on_click=lambda e, pid=pr.id: asyncio.ensure_future(
                    abrir_suministro(pid)
                ),
            ),
            ft.IconButton(
                icon="delete_outline",
                icon_color="red",
                icon_size=22,
                tooltip="Eliminar producto",
                on_click=lambda e, pid=pr.id, nom=pr.nombre: asyncio.ensure_future(
                    abrir_eliminar(pid, nom)
                ),
            ),
        ], vertical_alignment="center"),
        padding=10,
        bgcolor="#16191c",
        border_radius=10,
        border=ft.border.all(1, "red") if es_bajo else None,
    )