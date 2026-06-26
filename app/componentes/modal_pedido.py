# app/componentes/modal_pedido.py
import asyncio
import flet as ft


def build_modal_pedido(page: ft.Page, run_db, crud, models, refrescar_datos):
    """
    Modal para crear un pedido manual desde el dashboard.
    Maneja dos casos:
    - Cliente existente: busca por telefono y carga sus datos
    - Cliente nuevo: pide nombre y direccion antes de crear el pedido
    Retorna (modal, abrir_modal)
    """

    # ── Estado interno ────────────────────────────────────────
    _cliente_id     = {"id": None}
    _items_pedido   = []  # lista de {producto_id, nombre, precio, cantidad}

    # ── Campos del formulario ─────────────────────────────────
    inp_telefono    = ft.TextField(
        label="Teléfono del cliente *",
        width=280,
        prefix_icon="phone",
        keyboard_type=ft.KeyboardType.PHONE,
        hint_text="Ej: 999888777",
    )
    inp_nombre      = ft.TextField(label="Nombre completo *", width=280, visible=False)
    inp_direccion   = ft.TextField(label="Dirección de entrega *", width=280, visible=False)
    inp_referencia  = ft.TextField(label="Referencia (opcional)", width=280, visible=False)

    txt_cliente_info = ft.Text("", color="green", size=13)
    txt_error        = ft.Text("", color="red", size=12)

    # ── Seccion de productos ──────────────────────────────────
    dd_producto      = ft.Dropdown(
        label="Producto", width=220,
        options=[], bgcolor="#0b0d0f", color="white",
        visible=False,
    )
    inp_cantidad     = ft.TextField(
        label="Cantidad", width=80, value="1", visible=False
    )
    btn_agregar_item = ft.ElevatedButton(
        "Agregar", bgcolor="#1565c0", color="white",
        visible=False,
    )
    col_items        = ft.Column(spacing=6, scroll="always")
    txt_total        = ft.Text("Total: S/ 0.00", size=15, weight="bold",
                               color="amber", visible=False)

    seccion_campos_nuevos = ft.Column([
        inp_nombre, inp_direccion, inp_referencia
    ], spacing=8, visible=False)

    seccion_productos = ft.Column([
        ft.Divider(color="#2a2d30"),
        ft.Text("Productos del pedido:", size=13, color="grey"),
        ft.Row([dd_producto, inp_cantidad, btn_agregar_item],
               spacing=8, vertical_alignment="center"),
        col_items,
        txt_total,
    ], spacing=8, visible=False)

    # ── Recalcular total ──────────────────────────────────────
    def recalcular_total():
        total = sum(it["precio"] * it["cantidad"] for it in _items_pedido)
        txt_total.value = f"Total: S/ {total:.2f}"

    def construir_filas_items():
        col_items.controls.clear()
        for i, item in enumerate(_items_pedido):
            subtotal = item["precio"] * item["cantidad"]
            idx = i

            async def quitar(e, i=idx):
                _items_pedido.pop(i)
                construir_filas_items()
                recalcular_total()
                await page.update_async()

            col_items.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(item["nombre"], expand=True, size=13),
                        ft.Text(f"x{item['cantidad']}", width=35, size=13, color="grey"),
                        ft.Text(f"S/ {subtotal:.2f}", width=70, size=13, color="amber"),
                        ft.IconButton(
                            icon="remove_circle", icon_color="red",
                            icon_size=18, on_click=quitar,
                        ),
                    ], vertical_alignment="center", spacing=6),
                    bgcolor="#1a1d20", border_radius=8,
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                )
            )

    # ── Buscar cliente por telefono ───────────────────────────
    async def buscar_cliente(e=None):
        txt_error.value       = ""
        txt_cliente_info.value = ""
        telefono = inp_telefono.value.strip()

        if not telefono:
            txt_error.value = "Ingresa el teléfono del cliente."
            await page.update_async()
            return

        try:
            cliente = await run_db(lambda db: (
                db.query(models.Cliente)
                .filter(models.Cliente.telefono == telefono)
                .first()
            ))
            prods = await run_db(lambda db: (
                db.query(models.Producto)
                .filter(~models.Producto.nombre.startswith("[DESCONTINUADO]"))
                .all()
            ))

            # Cargar productos en dropdown
            dd_producto.options = [
                ft.dropdown.Option(
                    key=str(p.id),
                    text=f"{p.nombre} — S/ {p.precio_venta:.2f}"
                )
                for p in prods
            ]
            dd_producto.value = None

            if cliente:
                # Cliente existente
                _cliente_id["id"] = cliente.id
                txt_cliente_info.value = f"✅ Cliente: {cliente.nombre_completo}"
                seccion_campos_nuevos.visible = False
                inp_nombre.visible    = False
                inp_direccion.visible = False
                inp_referencia.visible = False
            else:
                # Cliente nuevo
                _cliente_id["id"] = None
                txt_cliente_info.value = "⚠️ Cliente nuevo — completa los datos"
                txt_cliente_info.color = "orange"
                seccion_campos_nuevos.visible = True
                inp_nombre.visible    = True
                inp_direccion.visible = True
                inp_referencia.visible = True

            # Mostrar seccion de productos
            dd_producto.visible      = True
            inp_cantidad.visible     = True
            btn_agregar_item.visible = True
            seccion_productos.visible = True
            txt_total.visible        = True

            await page.update_async()

        except Exception as ex:
            txt_error.value = f"Error: {ex}"
            await page.update_async()

    inp_telefono.on_submit = buscar_cliente

    # ── Agregar item al pedido ────────────────────────────────
    async def agregar_item(e):
        txt_error.value = ""
        if not dd_producto.value:
            txt_error.value = "Selecciona un producto."
            await page.update_async()
            return
        try:
            cant = int(inp_cantidad.value or 1)
            if cant <= 0:
                raise ValueError()

            prod_id = int(dd_producto.value)
            prods   = await run_db(lambda db: db.query(models.Producto).all())
            prod    = next((p for p in prods if p.id == prod_id), None)
            if not prod:
                return

            # Si ya existe el producto sumar cantidad
            existente = next(
                (it for it in _items_pedido if it["producto_id"] == prod_id), None
            )
            if existente:
                existente["cantidad"] += cant
            else:
                _items_pedido.append({
                    "producto_id": prod_id,
                    "nombre":      prod.nombre,
                    "precio":      prod.precio_venta or 0,
                    "cantidad":    cant,
                })

            construir_filas_items()
            recalcular_total()
            inp_cantidad.value = "1"
            dd_producto.value  = None
            await page.update_async()

        except ValueError:
            txt_error.value = "Cantidad inválida."
            await page.update_async()

    btn_agregar_item.on_click = agregar_item

    # ── Confirmar pedido ──────────────────────────────────────
    async def confirmar_pedido(e):
        txt_error.value = ""

        if not _items_pedido:
            txt_error.value = "Agrega al menos un producto."
            await page.update_async()
            return

        telefono = inp_telefono.value.strip()

        try:
            cliente_id = _cliente_id["id"]

            # Si es cliente nuevo, crear primero
            if not cliente_id:
                nombre    = inp_nombre.value.strip()
                direccion = inp_direccion.value.strip()
                ref       = inp_referencia.value.strip()

                if not nombre or not direccion:
                    txt_error.value = "Nombre y dirección son obligatorios."
                    await page.update_async()
                    return

                def crear_cliente(db):
                    nuevo = models.Cliente(
                        telefono=telefono,
                        nombre_completo=nombre,
                        direccion_exacta=direccion,
                        referencia_ubicacion=ref,
                    )
                    db.add(nuevo)
                    db.commit()
                    db.refresh(nuevo)
                    return nuevo.id

                cliente_id = await run_db(crear_cliente)

            # Crear pedido con sus items
            total = sum(it["precio"] * it["cantidad"] for it in _items_pedido)

            def crear_pedido(db):
                pedido = models.Pedido(
                    cliente_id=cliente_id,
                    total_pedido=total,
                    estado_logistico="recibido",
                    estado_pago="sin pagar",
                )
                db.add(pedido)
                db.flush()
                for it in _items_pedido:
                    detalle = models.DetallePedido(
                        pedido_id=pedido.id,
                        producto_id=it["producto_id"],
                        cantidad=it["cantidad"],
                    )
                    db.add(detalle)
                db.commit()
                return pedido.id

            pedido_id = await run_db(crear_pedido)

            # Limpiar modal
            modal_pedido.open = False
            _limpiar()
            snack = ft.SnackBar(
                ft.Text(f"✅ Pedido #{pedido_id} creado correctamente"),
                bgcolor="green"
            )
            page.overlay.append(snack)
            snack.open = True
            await refrescar_datos()

        except Exception as ex:
            txt_error.value = f"Error al crear pedido: {ex}"
            await page.update_async()

    # ── Limpiar modal ─────────────────────────────────────────
    def _limpiar():
        inp_telefono.value    = ""
        inp_nombre.value      = ""
        inp_direccion.value   = ""
        inp_referencia.value  = ""
        txt_cliente_info.value = ""
        txt_error.value       = ""
        txt_total.value       = "Total: S/ 0.00"
        _cliente_id["id"]     = None
        _items_pedido.clear()
        col_items.controls.clear()
        seccion_campos_nuevos.visible = False
        seccion_productos.visible     = False
        dd_producto.visible           = False
        inp_cantidad.visible          = False
        btn_agregar_item.visible      = False
        txt_total.visible             = False

    async def cerrar(e=None):
        modal_pedido.open = False
        _limpiar()
        await page.update_async()

    # ── Modal completo ────────────────────────────────────────
    modal_pedido = ft.AlertDialog(
        title=ft.Text("Nuevo Pedido Manual", weight="bold"),
        content=ft.Column([
            # Buscar cliente
            ft.Text("Buscar cliente por teléfono:", size=13, color="grey"),
            ft.Row([
                inp_telefono,
                ft.ElevatedButton(
                    "Buscar", bgcolor="#1565c0", color="white",
                    on_click=buscar_cliente,
                ),
            ], spacing=8, vertical_alignment="center"),
            txt_cliente_info,

            # Campos cliente nuevo
            seccion_campos_nuevos,

            # Productos
            seccion_productos,

            txt_error,
        ], spacing=10, tight=True, width=500, scroll="auto"),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar),
            ft.ElevatedButton(
                "Confirmar Pedido",
                bgcolor="green", color="white",
                on_click=confirmar_pedido,
            ),
        ],
    )

    async def abrir_modal(e=None):
        _limpiar()
        modal_pedido.open = True
        await page.update_async()

    return modal_pedido, abrir_modal