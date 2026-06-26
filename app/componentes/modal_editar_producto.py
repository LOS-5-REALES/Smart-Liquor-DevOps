# app/componentes/modal_editar_producto.py
import flet as ft


def build_modal_editar_producto(page: ft.Page, run_db, crud, models, refrescar_datos):
    """
    Modal para editar un producto existente (nombre, precio, stock mínimo).
    Incluye opción de descontinuar.
    Retorna (modal, abrir_modal_editar_producto)
    """
    _producto_id = {"valor": None}

    inp_nombre   = ft.TextField(label="Nombre del producto", width=300)
    inp_precio   = ft.TextField(label="Precio venta (S/)", width=145)
    inp_costo    = ft.TextField(label="Costo compra (S/)", width=145)
    inp_minimo   = ft.TextField(label="Stock mínimo", width=145)
    txt_error    = ft.Text("", color="red", size=12)

    async def guardar_cambios(e):
        txt_error.value = ""
        if not inp_nombre.value.strip():
            txt_error.value = "El nombre es obligatorio."
            await page.update_async()
            return
        try:
            pid = _producto_id["valor"]
            await run_db(lambda db: _actualizar_producto(
                db, pid,
                nombre=inp_nombre.value.strip(),
                precio_venta=float(inp_precio.value or 0),
                costo_compra=float(inp_costo.value or 0),
                stock_minimo=int(inp_minimo.value or 10),
            ))
            modal.open = False
            await refrescar_datos()
        except Exception as ex:
            txt_error.value = f"Error: {ex}"
            await page.update_async()

    async def descontinuar(e):
        try:
            pid = _producto_id["valor"]
            nombre_actual = inp_nombre.value.strip()
            if not nombre_actual.startswith("[DESCONTINUADO]"):
                nuevo_nombre = f"[DESCONTINUADO] {nombre_actual}"
                await run_db(lambda db: _actualizar_producto(
                    db, pid, nombre=nuevo_nombre,
                    precio_venta=float(inp_precio.value or 0),
                    costo_compra=float(inp_costo.value or 0),
                    stock_minimo=int(inp_minimo.value or 10),
                ))
            modal.open = False
            await refrescar_datos()
        except Exception as ex:
            txt_error.value = f"Error: {ex}"
            await page.update_async()

    async def cerrar(e=None):
        modal.open = False
        await page.update_async()

    modal = ft.AlertDialog(
        title=ft.Text("Editar Producto", weight="bold"),
        content=ft.Column([
            inp_nombre,
            ft.Row([inp_precio, inp_costo], spacing=10),
            inp_minimo,
            txt_error,
        ], spacing=10, tight=True, width=310),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar),
            ft.TextButton(
                "Descontinuar",
                on_click=descontinuar,
                style=ft.ButtonStyle(color="orange"),
            ),
            ft.ElevatedButton(
                "Guardar",
                on_click=guardar_cambios,
                bgcolor="#1565c0",
                color="white",
            ),
        ],
    )

    async def abrir_modal_editar_producto(producto_id: int):
        _producto_id["valor"] = producto_id
        txt_error.value = ""
        try:
            prod = await run_db(lambda db: db.query(models.Producto).filter(
                models.Producto.id == producto_id
            ).first())
            if prod:
                inp_nombre.value = prod.nombre
                inp_precio.value = str(prod.precio_venta or 0)
                inp_costo.value  = str(prod.costo_compra or 0) if hasattr(prod, 'costo_compra') else "0"
                inp_minimo.value = str(prod.stock_minimo or 10)
            modal.open = True
            await page.update_async()
        except Exception as ex:
            print(f"[ERROR abrir_modal_editar_producto] {ex}")

    return modal, abrir_modal_editar_producto


def _actualizar_producto(db, producto_id, nombre, precio_venta, costo_compra, stock_minimo):
    from models import Producto
    prod = db.query(Producto).filter(Producto.id == producto_id).first()
    if prod:
        prod.nombre       = nombre
        prod.precio_venta = precio_venta
        prod.stock_minimo = stock_minimo
        if hasattr(prod, 'costo_compra'):
            prod.costo_compra = costo_compra
        db.commit()