# app/componentes/filtro_fecha.py
import flet as ft
from datetime import datetime, timedelta


def build_filtro_fecha(on_filtrar, on_pdf, on_limpiar):
    """
    Barra de filtro con botones rapidos y campos opcionales.
    Retorna (inp_fecha_inicio, inp_fecha_fin, txt_error, col_filtro)
    """
    inp_fecha_inicio = ft.TextField(
        label="Desde (DD/MM/AAAA)", width=145, value=""
    )
    inp_fecha_fin = ft.TextField(
        label="Hasta (DD/MM/AAAA)", width=145, value=""
    )
    txt_error = ft.Text("", color="red", size=11)
    row_personalizado = ft.Row(
        [inp_fecha_inicio, inp_fecha_fin,
         ft.ElevatedButton("Aplicar", bgcolor="#1565c0", color="white",
                           height=36, on_click=on_filtrar)],
        spacing=8, visible=False
    )

    def set_fecha(inicio: str, fin: str):
        inp_fecha_inicio.value = inicio
        inp_fecha_fin.value    = fin

    async def btn_hoy(e):
        hoy = datetime.now().strftime("%d/%m/%Y")
        set_fecha(hoy, hoy)
        row_personalizado.visible = False
        await on_filtrar(e)
        await e.page.update_async()

    async def btn_semana(e):
        hoy   = datetime.now()
        inicio = (hoy - timedelta(days=7)).strftime("%d/%m/%Y")
        fin    = hoy.strftime("%d/%m/%Y")
        set_fecha(inicio, fin)
        row_personalizado.visible = False
        await on_filtrar(e)
        await e.page.update_async()

    async def btn_mes(e):
        hoy   = datetime.now()
        inicio = hoy.replace(day=1).strftime("%d/%m/%Y")
        fin    = hoy.strftime("%d/%m/%Y")
        set_fecha(inicio, fin)
        row_personalizado.visible = False
        await on_filtrar(e)
        await e.page.update_async()

    async def btn_personalizado(e):
        row_personalizado.visible = not row_personalizado.visible
        await e.page.update_async()

    async def btn_limpiar(e):
        set_fecha("", "")
        row_personalizado.visible = False
        await on_limpiar(e)
        await e.page.update_async()

    # Estilo compartido de botones
    def quick_btn(texto, handler, color="#2a2d30"):
        return ft.ElevatedButton(
            texto, height=36, bgcolor=color,
            color="white", on_click=handler,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))
        )

    col_filtro = ft.Column([
        ft.Row([
            quick_btn("Hoy",           btn_hoy,           "#1E5631"),
            quick_btn("Esta semana",   btn_semana,        "#1565c0"),
            quick_btn("Este mes",      btn_mes,           "#4A235A"),
            quick_btn("Personalizado", btn_personalizado, "#7D3C00"),
            ft.ElevatedButton(
                "PDF", icon="picture_as_pdf",
                bgcolor="#c62828", color="white",
                height=36, on_click=on_pdf,
            ),
            ft.TextButton("Limpiar", on_click=btn_limpiar),
        ], spacing=8),
        row_personalizado,
        txt_error,
    ], spacing=6)

    return inp_fecha_inicio, inp_fecha_fin, txt_error, col_filtro