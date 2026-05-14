import asyncio
import flet as ft
from sqlalchemy.orm import Session, joinedload
from database import engine
import models
import crud


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


COLORES_ESTADO = {
    "recibido":  "#f57c00",
    "en ruta":   "#1565c0",
    "entregado": "#2e7d32",
    "cancelado": "#c62828",
}


async def main(page: ft.Page):
    page.title = "Smart-Liquor DevOps - Dashboard"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0b0d0f"
    page.padding = 25

    txt_ventas  = ft.Text("S/ 0.00", size=30, weight="bold", color="amber")
    txt_pedidos = ft.Text("0",       size=30, weight="bold")
    txt_alertas = ft.Text("0",       size=30, weight="bold", color="red")

    lista_pedidos_ui    = ft.Column(spacing=10, scroll="always")
    lista_inventario_ui = ft.Column(spacing=10, scroll="always")

    # ─── MODAL SUMINISTRO (tu código original, sin cambios) ───
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
        actions=[ft.ElevatedButton("Guardar", on_click=guardar_suministro,
                                   bgcolor="green", color="white")],
    )
    page.overlay.append(modal)

    async def abrir_suministro(pid: int):
        id_actual.value   = str(pid)
        input_stock.value = "10"
        modal.open        = True
        await page.update_async()

    # ─── MODAL NUEVO PRODUCTO ─────────────────────────────────
    inp_nombre = ft.TextField(label="Nombre *", width=300)
    inp_marca  = ft.TextField(label="Marca",    width=300)
    inp_precio = ft.TextField(label="Precio venta (S/)", width=145, value="0.0")
    inp_costo  = ft.TextField(label="Costo compra (S/)", width=145, value="0.0")
    inp_stock_nuevo = ft.TextField(label="Stock inicial", width=145, value="0")
    inp_minimo = ft.TextField(label="Stock minimo",  width=145, value="10")
    txt_error  = ft.Text("", color="red", size=12)

    async def guardar_nuevo_producto(e):
        txt_error.value = ""
        if not inp_nombre.value.strip():
            txt_error.value = "El nombre es obligatorio."
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
            inp_nombre.value = ""
            inp_marca.value  = ""
            inp_precio.value = "0.0"
            inp_costo.value  = "0.0"
            inp_stock_nuevo.value = "0"
            inp_minimo.value = "10"
            await refrescar_datos()
        except Exception as ex:
            txt_error.value = f"Error: {ex}"
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
            txt_error,
        ], spacing=10, tight=True, width=310),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_crear),
            ft.ElevatedButton("Crear", on_click=guardar_nuevo_producto,
                              bgcolor="green", color="white"),
        ],
    )
    page.overlay.append(modal_crear)

    async def abrir_crear(e=None):
        modal_crear.open = True
        await page.update_async()

    # ─── MODAL ELIMINAR PRODUCTO ──────────────────────────────
    id_a_eliminar    = ft.Text("", visible=False)
    txt_msg_eliminar = ft.Text("", size=14)

    async def confirmar_eliminar(e):
        resultado = await run_db(
            lambda db: crud.eliminar_producto(db, int(id_a_eliminar.value))
        )
        modal_eliminar.open = False
        if resultado == "descontinuado":
            msg = "Marcado como DESCONTINUADO (tiene pedidos vinculados)"
            color = "orange"
        else:
            msg = "Producto eliminado correctamente"
            color = "green"
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
            ft.ElevatedButton("Eliminar", on_click=confirmar_eliminar,
                              bgcolor="red", color="white"),
        ],
    )
    page.overlay.append(modal_eliminar)

    async def abrir_eliminar(pid: int, nombre: str):
        id_a_eliminar.value = str(pid)
        txt_msg_eliminar.value = (
            f'¿Eliminar "{nombre}"?\n\n'
            "Si tiene pedidos vinculados se marcara como DESCONTINUADO."
        )
        modal_eliminar.open = True
        await page.update_async()

    # ─── MÉTRICAS ─────────────────────────────────────────────
    async def cambiar_estado(pedido_id: int, nuevo_estado: str):
        await run_db(lambda db: crud.actualizar_estado_pedido(db, pedido_id, nuevo_estado))
        peds = await run_db(lambda db: db.query(models.Pedido).all())
        ventas = sum(p.total_pedido for p in peds if p.total_pedido)
        txt_ventas.value  = f"S/ {ventas:,.2f}"
        txt_pedidos.value = str(len(peds))
        await page.update_async()

    # ─── REFRESCO PRINCIPAL ───────────────────────────────────
    async def refrescar_datos(e=None):
        try:
            prods = await run_db(lambda db: db.query(models.Producto).all())
            peds  = await run_db(lambda db: (
                db.query(models.Pedido)
                .options(
                    joinedload(models.Pedido.cliente),
                    joinedload(models.Pedido.items)
                        .joinedload(models.DetallePedido.producto),
                )
                .order_by(models.Pedido.id.desc())
                .all()
            ))

            # Metricas
            criticos = [p for p in prods if (p.stock_actual or 0) <= (p.stock_minimo or 10)]
            txt_alertas.value = str(len(criticos))
            txt_pedidos.value = str(len(peds))
            ventas = sum(p.total_pedido for p in peds if p.total_pedido)
            txt_ventas.value  = f"S/ {ventas:,.2f}"

            # ── Pedidos (tu código original sin cambios) ──
            lista_pedidos_ui.controls.clear()
            for p in peds:
                nombre_cliente = p.cliente.nombre_completo if p.cliente else "Anonimo"
                total          = p.total_pedido or 0.0
                estado_actual  = p.estado_logistico or "recibido"
                color_estado   = COLORES_ESTADO.get(estado_actual, "grey")

                filas_items = []
                if p.items:
                    for item in p.items:
                        nombre_prod = item.producto.nombre if item.producto else "Producto eliminado"
                        precio_unit = (item.producto.precio_venta or 0) if item.producto else 0
                        subtotal    = precio_unit * (item.cantidad or 0)
                        filas_items.append(ft.Row(
                            controls=[
                                ft.Icon("circle", size=7, color="amber"),
                                ft.Text(nombre_prod, expand=True, size=13),
                                ft.Text(f"x{item.cantidad}", width=40, size=13,
                                        color="grey", text_align="right"),
                                ft.Text(f"S/ {subtotal:.2f}", width=75, size=13,
                                        color="amber", text_align="right"),
                            ],
                            spacing=8, vertical_alignment="center",
                        ))
                else:
                    filas_items.append(
                        ft.Text("Sin items registrados", color="grey", size=12, italic=True)
                    )

                panel_detalle = ft.Container(
                    visible=False,
                    content=ft.Column(controls=[
                        ft.Divider(height=10, color="#2a2d30"),
                        ft.Row(controls=[
                            ft.Text("PRODUCTO", size=11, color="#555", expand=True),
                            ft.Text("CANT.",    size=11, color="#555", width=40, text_align="right"),
                            ft.Text("SUBTOTAL", size=11, color="#555", width=75, text_align="right"),
                        ], spacing=8),
                        *filas_items,
                    ], spacing=6),
                    padding=ft.padding.only(left=4, right=4, top=0, bottom=6),
                )

                btn_expand = ft.IconButton(icon="keyboard_arrow_down",
                                           icon_color="white", icon_size=22,
                                           tooltip="Ver detalle del pedido")

                async def toggle(e, _panel=panel_detalle, _btn=btn_expand):
                    _panel.visible  = not _panel.visible
                    _btn.icon       = "keyboard_arrow_up" if _panel.visible else "keyboard_arrow_down"
                    _btn.icon_color = "amber"             if _panel.visible else "white"
                    await page.update_async()

                btn_expand.on_click = toggle

                dropdown_estado = ft.Dropdown(
                    value=estado_actual, width=140,
                    content_padding=ft.padding.symmetric(horizontal=10, vertical=4),
                    options=[
                        ft.dropdown.Option(key="recibido",  text="Recibido"),
                        ft.dropdown.Option(key="en camino", text="En camino"),
                        ft.dropdown.Option(key="entregado", text="Entregado"),
                        ft.dropdown.Option(key="cancelado", text="Cancelado"),
                    ],
                    border_color=color_estado, color="white", bgcolor="#0b0d0f",
                )

                async def _on_estado_change(e, pid: int, _dd=dropdown_estado):
                    nuevo = e.control.value
                    _dd.border_color = COLORES_ESTADO.get(nuevo, "grey")
                    await page.update_async()
                    await cambiar_estado(pid, nuevo)

                dropdown_estado.on_change = lambda e, pid=p.id, _dd=dropdown_estado: (
                    asyncio.ensure_future(_on_estado_change(e, pid, _dd))
                )

                lista_pedidos_ui.controls.append(ft.Container(
                    content=ft.Column(controls=[
                        ft.Row(controls=[
                            ft.Icon("shopping_cart", color="orange", size=20),
                            ft.Column(controls=[
                                ft.Text(f"Pedido #{p.id}  —  {nombre_cliente}",
                                        weight="bold", size=14),
                                ft.Row(controls=[
                                    ft.Text(f"S/ {total:.2f}", color="amber", size=13),
                                    dropdown_estado,
                                ], spacing=10, vertical_alignment="center"),
                            ], expand=True, spacing=4),
                            btn_expand,
                        ], vertical_alignment="center", spacing=12),
                        panel_detalle,
                    ], spacing=0),
                    bgcolor="#16191c", border_radius=10,
                    padding=ft.padding.symmetric(horizontal=14, vertical=10),
                ))

            # ── Inventario (NUEVO: badge alerta + boton eliminar) ──
            lista_inventario_ui.controls.clear()
            for pr in prods:
                es_bajo = (pr.stock_actual or 0) <= (pr.stock_minimo or 10)
                es_desc = pr.nombre.startswith("[DESCONTINUADO]")

                lista_inventario_ui.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(pr.nombre, weight="bold",
                                    color="#666" if es_desc else "white"),
                            ft.Row([
                                ft.Text(f"Stock: {pr.stock_actual}",
                                        color="red" if es_bajo else "#aaa", size=13),
                                # Badge STOCK BAJO visible solo cuando aplica
                                ft.Container(
                                    visible=es_bajo and not es_desc,
                                    content=ft.Text("STOCK BAJO", size=10, color="white"),
                                    bgcolor="red", border_radius=4,
                                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                                ),
                            ], spacing=8),
                        ], expand=True, spacing=2),
                        # Boton sumar stock
                        ft.IconButton(
                            icon="add_circle", icon_color="green", icon_size=22,
                            tooltip="Sumar stock",
                            visible=not es_desc,
                            on_click=lambda e, pid=pr.id: asyncio.ensure_future(
                                abrir_suministro(pid)
                            ),
                        ),
                        # Boton eliminar
                        ft.IconButton(
                            icon="delete_outline", icon_color="red", icon_size=22,
                            tooltip="Eliminar producto",
                            on_click=lambda e, pid=pr.id, nom=pr.nombre: asyncio.ensure_future(
                                abrir_eliminar(pid, nom)
                            ),
                        ),
                    ], vertical_alignment="center"),
                    padding=10, bgcolor="#16191c", border_radius=10,
                ))

            await page.update_async()

        except Exception as ex:
            print(f"[UI ERROR] {ex}")

    # ─── LAYOUT ───────────────────────────────────────────────
    await page.add_async(
        ft.Row(controls=[
            ft.Column([
                ft.Text("Smart-Liquor Dashboard", size=28, weight="bold"),
                ft.Text("Logistica Chincha  •  Supabase Cloud", color="grey"),
            ]),
            ft.IconButton("refresh", on_click=refrescar_datos, tooltip="Actualizar"),
        ], alignment="spaceBetween"),

        ft.Divider(height=20, color="#232629"),

        ft.Row([
            ft.Column([ft.Text("VENTAS TOTALES", size=10, color="grey"), txt_ventas],  expand=True),
            ft.Column([ft.Text("PEDIDOS",        size=10, color="grey"), txt_pedidos], expand=True),
            ft.Column([ft.Text("STOCK CRITICO",  size=10, color="grey"), txt_alertas], expand=True),
        ]),

        ft.Divider(height=20, color="#232629"),

        ft.Row(controls=[
            ft.Column([
                ft.Text("Pedidos Recientes", size=18, weight="bold"),
                ft.Container(content=lista_pedidos_ui, height=450),
            ], expand=2),
            ft.Column([
                # Header inventario con boton Nuevo Producto
                ft.Row([
                    ft.Text("Inventario", size=18, weight="bold", expand=True),
                    ft.ElevatedButton(
                        "+ Nuevo",
                        bgcolor="green", color="white", height=32,
                        on_click=lambda e: asyncio.ensure_future(abrir_crear()),
                    ),
                ], vertical_alignment="center"),
                ft.Container(content=lista_inventario_ui, height=450),
            ], expand=1),
        ], vertical_alignment="start", spacing=30),
    )

    await refrescar_datos()