import flet as ft


def build_modal_suministro(page: ft.Page, run_db, crud, refrescar_datos):
    """
    Crea el modal para sumar stock a un producto.

    Parametros:
        page          -- objeto Page de Flet
        run_db        -- funcion helper para ejecutar consultas async
        crud          -- modulo crud con sumar_stock_producto
        refrescar_datos -- funcion para actualizar el dashboard

    Retorna (modal, abrir_suministro) para que ui.py
    agregue el modal al overlay y llame abrir_suministro(pid).
    """
    input_stock = ft.TextField(label="Cantidad a sumar", value="10", width=150)
    id_actual   = ft.Text("", visible=False)

    async def guardar_suministro(e):
        await run_db(lambda db: crud.sumar_stock_producto(
            db, int(id_actual.value), int(input_stock.value)
        ))
        modal.open = False
        await refrescar_datos()

    modal = ft.AlertDialog(
        title=ft.Text("Sumar Stock al Producto"),
        content=input_stock,
        actions=[
            ft.ElevatedButton(
                "Guardar",
                on_click=guardar_suministro,
                bgcolor="green",
                color="white",
            )
        ],
    )

    async def abrir_suministro(pid: int):
        id_actual.value   = str(pid)
        input_stock.value = "10"
        modal.open        = True
        await page.update_async()

    return modal, abrir_suministro