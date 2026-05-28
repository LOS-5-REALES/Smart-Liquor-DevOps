# app/componentes/modal_producto.py
import flet as ft


def build_modal_producto(page: ft.Page, run_db, crud, refrescar_datos):
    """
    Crea los modales para crear y eliminar productos.
    Retorna (modal_crear, modal_eliminar, abrir_crear, abrir_eliminar)
    """
    # ── MODAL CREAR ───────────────────────────────────────────
    inp_nombre      = ft.TextField(label="Nombre *", width=300)
    inp_marca       = ft.TextField(label="Marca",    width=300)
    inp_precio      = ft.TextField(label="Precio venta (S/)", width=145, value="0.0")
    inp_costo       = ft.TextField(label="Costo compra (S/)", width=145, value="0.0")
    inp_stock_nuevo = ft.TextField(label="Stock inicial",     width=145, value="0")
    inp_minimo      = ft.TextField(label="Stock minimo",      width=145, value="10")
    txt_error_prod  = ft.Text("", color="red", size=12)

    async def guardar_nuevo_producto(e):
        txt_error_prod.value = ""
        if not inp_nombre.value.strip():
            txt_error_prod.value = "El nombre es obligatorio."
            await page.update_async()
            return
        try:
            await run_db(lambda db: crud.crear_producto(
                db,
                nombre=inp_nombre.value.strip(),
                marca=inp_marca.value.strip(),
                precio_venta=float(inp_precio.value or 0),
                costo_compra=float(inp_costo.value or 0),
                stock_actual=int(inp_stock_nuevo.value or 0),
                stock_minimo=int(inp_minimo.value or 10),
            ))
            modal_crear.open = False
            inp_nombre.value = inp_marca.value = ""
            inp_precio.value = inp_costo.value = "0.0"
            inp_stock_nuevo.value = "0"
            inp_minimo.value = "10"
            await refrescar_datos()
        except Exception as ex:
            txt_error_prod.value = f"Error: {ex}"
            await page.update_async()

    async def cerrar_crear(e=None):
        modal_crear.open = False
        await page.update_async()

    modal_crear = ft.AlertDialog(
        title=ft.Text("Nuevo Producto"),
        content=ft.Column([
            inp_nombre,
            inp_marca,
            ft.Row([inp_precio, inp_costo], spacing=10),
            ft.Row([inp_stock_nuevo, inp_minimo], spacing=10),
            txt_error_prod,
        ], spacing=10, tight=True, width=310),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_crear),
            ft.ElevatedButton(
                "Crear",
                on_click=guardar_nuevo_producto,
                bgcolor="green",
                color="white",
            ),
        ],
    )

    async def abrir_crear(e=None):
        modal_crear.open = True
        await page.update_async()

    # ── MODAL ELIMINAR ────────────────────────────────────────
    id_a_eliminar    = ft.Text("", visible=False)
    txt_msg_eliminar = ft.Text("", size=14)

    async def confirmar_eliminar(e):
        resultado = await run_db(
            lambda db: crud.eliminar_producto(db, int(id_a_eliminar.value))
        )
        modal_eliminar.open = False
        msg   = ("Marcado como DESCONTINUADO"
                 if resultado == "descontinuado"
                 else "Producto eliminado correctamente")
        color = "orange" if resultado == "descontinuado" else "green"
        snack = ft.SnackBar(ft.Text(msg), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        await refrescar_datos()

    async def cerrar_eliminar(e=None):
        modal_eliminar.open = False
        await page.update_async()

    modal_eliminar = ft.AlertDialog(
        title=ft.Text("Eliminar Producto", color="red"),
        content=txt_msg_eliminar,
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_eliminar),
            ft.ElevatedButton(
                "Eliminar",
                on_click=confirmar_eliminar,
                bgcolor="red",
                color="white",
            ),
        ],
    )

    async def abrir_eliminar(pid: int, nombre: str):
        id_a_eliminar.value    = str(pid)
        txt_msg_eliminar.value = (
            f'¿Eliminar "{nombre}"?\n\n'
            "Si tiene pedidos vinculados se marcara como DESCONTINUADO."
        )
        modal_eliminar.open = True
        await page.update_async()

    return modal_crear, modal_eliminar, abrir_crear, abrir_eliminar