# app/componentes/modal_editar.py
import flet as ft


def build_modal_editar(page: ft.Page, run_db, crud, models, refrescar_datos):
    """
    Crea el modal para editar items de un pedido.
    Retorna (modal_editar, cargar_modal_editar)
    """
    col_items_editar  = ft.Column(spacing=8, scroll="always", height=300)
    txt_total_editar  = ft.Text("Total: S/ 0.00", size=16, weight="bold", color="amber")
    txt_error_editar  = ft.Text("", color="red", size=12)
    _pedido_id_editar = {"id": None}

    dd_nuevo_prod      = ft.Dropdown(
        label="Agregar producto", width=220,
        options=[], bgcolor="#0b0d0f", color="white",
    )
    inp_nueva_cantidad = ft.TextField(label="Cantidad", width=90, value="1")

    async def cargar_modal_editar(pedido_id: int):
        _pedido_id_editar["id"] = pedido_id
        txt_error_editar.value  = ""

        pedido = await run_db(lambda db: crud.obtener_pedido_con_items(db, pedido_id))
        prods  = await run_db(lambda db: db.query(models.Producto).all())

        dd_nuevo_prod.options = [
            ft.dropdown.Option(
                key=str(p.id),
                text=f"{p.nombre} (S/{p.precio_venta or 0:.2f})"
            )
            for p in prods if not p.nombre.startswith("[DESCONTINUADO]")
        ]
        dd_nuevo_prod.value = None

        col_items_editar.controls.clear()
        total = pedido.total_pedido or 0.0
        txt_total_editar.value = f"Total: S/ {total:.2f}"

        if pedido.items:
            for item in pedido.items:
                nombre_prod = item.producto.nombre if item.producto else "Producto eliminado"
                precio_unit = (item.producto.precio_venta or 0) if item.producto else 0
                subtotal    = precio_unit * (item.cantidad or 0)

                inp_cant = ft.TextField(
                    value=str(item.cantidad), width=70,
                    text_align="center",
                )

                async def guardar_cantidad(e, did=item.id, inp=inp_cant):
                    try:
                        nueva = int(inp.value or 0)
                        await run_db(lambda db: crud.actualizar_cantidad_item(db, did, nueva))
                        await cargar_modal_editar(_pedido_id_editar["id"])
                    except Exception as ex:
                        txt_error_editar.value = f"Error: {ex}"
                        await page.update_async()

                async def quitar_item(e, did=item.id):
                    await run_db(lambda db: crud.eliminar_item_pedido(db, did))
                    await cargar_modal_editar(_pedido_id_editar["id"])

                col_items_editar.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(nombre_prod, size=13, weight="bold"),
                                ft.Text(
                                    f"S/ {precio_unit:.2f} c/u  →  subtotal S/ {subtotal:.2f}",
                                    size=11, color="#aaa"
                                ),
                            ], expand=True, spacing=1),
                            inp_cant,
                            ft.IconButton(
                                icon="check_circle", icon_color="green",
                                icon_size=20, tooltip="Guardar cantidad",
                                on_click=guardar_cantidad,
                            ),
                            ft.IconButton(
                                icon="remove_circle", icon_color="red",
                                icon_size=20, tooltip="Quitar item",
                                on_click=quitar_item,
                            ),
                        ], vertical_alignment="center", spacing=6),
                        bgcolor="#1a1d20", border_radius=8,
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    )
                )
        else:
            col_items_editar.controls.append(
                ft.Text("Sin items — agrega productos abajo.", color="grey", italic=True)
            )

        modal_editar.open = True
        await page.update_async()

    async def agregar_nuevo_item(e):
        txt_error_editar.value = ""
        if not dd_nuevo_prod.value:
            txt_error_editar.value = "Selecciona un producto."
            await page.update_async()
            return
        try:
            cant = int(inp_nueva_cantidad.value or 1)
            if cant <= 0:
                raise ValueError("La cantidad debe ser mayor a 0.")
            await run_db(lambda db: crud.agregar_item_pedido(
                db, _pedido_id_editar["id"],
                int(dd_nuevo_prod.value), cant,
            ))
            inp_nueva_cantidad.value = "1"
            await cargar_modal_editar(_pedido_id_editar["id"])
        except Exception as ex:
            txt_error_editar.value = f"Error: {ex}"
            await page.update_async()

    async def cerrar_editar(e=None):
        modal_editar.open = False
        await refrescar_datos()

    modal_editar = ft.AlertDialog(
        title=ft.Text("Editar Pedido"),
        content=ft.Column([
            txt_total_editar,
            ft.Divider(color="#2a2d30"),
            ft.Text("Items del pedido:", size=13, color="grey"),
            col_items_editar,
            ft.Divider(color="#2a2d30"),
            ft.Text("Agregar producto:", size=13, color="grey"),
            ft.Row([
                dd_nuevo_prod,
                inp_nueva_cantidad,
                ft.ElevatedButton(
                    "Agregar",
                    bgcolor="#1565c0",
                    color="white",
                    on_click=agregar_nuevo_item,
                ),
            ], spacing=8, vertical_alignment="center"),
            txt_error_editar,
        ], spacing=10, tight=True, width=480),
        actions=[
            ft.ElevatedButton(
                "Cerrar y guardar",
                on_click=cerrar_editar,
                bgcolor="green",
                color="white",
            ),
        ],
    )

    return modal_editar, cargar_modal_editar