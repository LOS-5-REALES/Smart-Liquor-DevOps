# app/componentes/metricas.py
import flet as ft


def build_metricas():
    """
    Crea las metricas del dashboard.
    Retorna (txt_ventas, txt_pedidos, txt_alertas, txt_pendientes,
             txt_entregados, row_metricas)
    """
    # ── Metrica 1: Ventas del periodo ─────────────────────────
    txt_ventas = ft.Text("S/ 0.00", size=28, weight="bold", color="amber")

    # ── Metrica 2: Pedidos pendientes (recibido + en camino) ──
    txt_pendientes = ft.Text("0", size=28, weight="bold", color="orange")

    # ── Metrica 3: Entregados en el periodo ───────────────────
    txt_entregados = ft.Text("0", size=28, weight="bold", color="green")

    # ── Metrica 4: Stock critico ──────────────────────────────
    txt_alertas = ft.Text("0", size=28, weight="bold", color="red")

    # ── Metrica 5: Pedidos totales (oculto, usado internamente)
    txt_pedidos = ft.Text("0", size=28, weight="bold")

    row = ft.Row([
        ft.Container(
            expand=True,
            bgcolor="#16191c",
            border_radius=10,
            padding=15,
            content=ft.Column([
                ft.Text("VENTAS DEL PERIODO", size=10, color="grey"),
                txt_ventas,
            ], spacing=4),
        ),
        ft.Container(
            expand=True,
            bgcolor="#16191c",
            border_radius=10,
            padding=15,
            content=ft.Column([
                ft.Text("PEDIDOS PENDIENTES", size=10, color="grey"),
                txt_pendientes,
                ft.Text("recibido + en camino", size=9, color="#555"),
            ], spacing=4),
        ),
        ft.Container(
            expand=True,
            bgcolor="#16191c",
            border_radius=10,
            padding=15,
            content=ft.Column([
                ft.Text("ENTREGADOS", size=10, color="grey"),
                txt_entregados,
                ft.Text("en el periodo", size=9, color="#555"),
            ], spacing=4),
        ),
        ft.Container(
            expand=True,
            bgcolor="#16191c",
            border_radius=10,
            padding=15,
            border=ft.border.all(1, "red"),
            content=ft.Column([
                ft.Text("STOCK CRITICO", size=10, color="grey"),
                txt_alertas,
                ft.Text("productos bajo minimo", size=9, color="#555"),
            ], spacing=4),
        ),
    ], spacing=12)

    return txt_ventas, txt_pedidos, txt_alertas, txt_pendientes, txt_entregados, row