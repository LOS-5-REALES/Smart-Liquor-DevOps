import flet as ft


def build_filtro_fecha(on_filtrar, on_pdf, on_limpiar):
    """
    Crea la barra de filtro por fecha con los botones.
    
    Parametros:
        on_filtrar  -- funcion async que se llama al presionar Filtrar
        on_pdf      -- funcion async que se llama al presionar Generar PDF
        on_limpiar  -- funcion async que se llama al presionar Limpiar

    Retorna (inp_fecha_inicio, inp_fecha_fin, txt_error, row_filtro)
    para que ui.py pueda leer los valores de los inputs.
    """
    inp_fecha_inicio = ft.TextField(
        label="Desde (DD/MM/AAAA)", width=160, value=""
    )
    inp_fecha_fin = ft.TextField(
        label="Hasta (DD/MM/AAAA)", width=160, value=""
    )
    txt_error = ft.Text("", color="red", size=11)

    row = ft.Row([
        inp_fecha_inicio,
        inp_fecha_fin,
        ft.ElevatedButton(
            "Filtrar",
            bgcolor="#1565c0",
            color="white",
            height=40,
            on_click=on_filtrar,
        ),
        ft.ElevatedButton(
            "Generar PDF",
            icon="picture_as_pdf",
            bgcolor="#c62828",
            color="white",
            on_click=on_pdf,
        ),
        ft.TextButton("Limpiar", on_click=on_limpiar),
    ], spacing=8, vertical_alignment="center")

    return inp_fecha_inicio, inp_fecha_fin, txt_error, row