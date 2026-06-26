# app/componentes/metricas.py
import flet as ft


def build_metricas():
    txt_ventas     = ft.Text("S/ 0.00", size=26, weight="bold", color="amber")
    txt_pendientes = ft.Text("0", size=26, weight="bold", color="orange")
    txt_entregados = ft.Text("0", size=26, weight="bold", color="green")
    txt_alertas    = ft.Text("0", size=26, weight="bold", color="red")
    txt_pedidos    = ft.Text("0", size=26, weight="bold")

    def card(label, valor_txt, sub=""):
        return ft.Container(
            expand=True,
            bgcolor="#16191c",
            border_radius=10,
            padding=12,
            content=ft.Column([
                ft.Text(label, size=10, color="grey"),
                valor_txt,
                ft.Text(sub, size=9, color="#555") if sub else ft.Container(height=0),
            ], spacing=3),
        )

    # Fila para desktop
    row_desktop = ft.Row([
        card("VENTAS DEL PERIODO", txt_ventas),
        card("PEDIDOS PENDIENTES", txt_pendientes, "recibido + en camino"),
        card("ENTREGADOS",         txt_entregados, "en el periodo"),
        card("STOCK CRITICO",      txt_alertas,    "productos bajo minimo"),
    ], spacing=10)

    # Columna para movil — 2x2
    col_mobile = ft.Column([
        ft.Row([
            card("VENTAS DEL PERIODO", txt_ventas),
            card("PEDIDOS PENDIENTES", txt_pendientes),
        ], spacing=8),
        ft.Row([
            card("ENTREGADOS",    txt_entregados),
            card("STOCK CRITICO", txt_alertas),
        ], spacing=8),
    ], spacing=8)

    # Wrapper responsivo
    wrapper = ft.Container(content=row_desktop)

    def actualizar(page_width):
        if page_width and page_width < 700:
            wrapper.content = col_mobile
        else:
            wrapper.content = row_desktop

    return txt_ventas, txt_pedidos, txt_alertas, txt_pendientes, txt_entregados, wrapper, actualizar