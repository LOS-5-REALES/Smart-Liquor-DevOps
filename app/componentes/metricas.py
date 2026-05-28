import flet as ft


def build_metricas():
    """
    Crea los 3 textos de metricas y el Row que los contiene.
    Retorna (txt_ventas, txt_pedidos, txt_alertas, row_metricas)
    para que ui.py pueda actualizar los valores.
    """
    txt_ventas  = ft.Text("S/ 0.00", size=30, weight="bold", color="amber")
    txt_pedidos = ft.Text("0",       size=30, weight="bold")
    txt_alertas = ft.Text("0",       size=30, weight="bold", color="red")

    row = ft.Row([
        ft.Column([
            ft.Text("VENTAS TOTALES", size=10, color="grey"),
            txt_ventas
        ], expand=True),
        ft.Column([
            ft.Text("PEDIDOS", size=10, color="grey"),
            txt_pedidos
        ], expand=True),
        ft.Column([
            ft.Text("STOCK CRITICO", size=10, color="grey"),
            txt_alertas
        ], expand=True),
    ])

    return txt_ventas, txt_pedidos, txt_alertas, row