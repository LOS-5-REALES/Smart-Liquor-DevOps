import asyncio
from datetime import datetime
import flet as ft
from sqlalchemy.orm import Session, joinedload
from database import engine
import models
import crud
from reports import generar_pdf_pedidos


async def run_db(fn):
    def _execute():
        with Session(engine) as db:
            return fn(db)
    return await asyncio.to_thread(_execute)


COLORES_ESTADO = {
    "recibido":  "#f57c00",
    "en ruta":   "#1565c0",
    "en camino": "#1565c0",
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
    _todos_los_pedidos  = []

    # ─── FILTRO POR FECHA ─────────────────────────────────────
    inp_fecha_inicio = ft.TextField(label="Desde (DD/MM/AAAA)", width=160, value="")
    inp_fecha_fin    = ft.TextField(label="Hasta (DD/MM/AAAA)", width=160, value="")
    txt_error_fecha  = ft.Text("", color="red", size=11)

    

    def parsear_fecha(texto):
        texto = texto.strip()
        if not texto:
            return None
        try:
            return datetime.strptime(texto, "%d/%m/%Y")
        except ValueError:
            return None

    def filtrar_pedidos(peds):
        desde = parsear_fecha(inp_fecha_inicio.value)
        hasta = parsear_fecha(inp_fecha_fin.value)
        if not desde and not hasta:
            return peds
        resultado = []
        for p in peds:
            if not p.fecha_hora:
                continue
            fh = p.fecha_hora if isinstance(p.fecha_hora, datetime) else datetime.fromisoformat(str(p.fecha_hora))
            fh_solo = fh.replace(hour=0, minute=0, second=0, microsecond=0)
            if desde and hasta and desde <= fh_solo <= hasta:
                resultado.append(p)
            elif desde and not hasta and fh_solo >= desde:
                resultado.append(p)
            elif hasta and not desde and fh_solo <= hasta:
                resultado.append(p)
        return resultado


    async def aplicar_filtro(e=None):
        txt_error_fecha.value = ""
        desde = parsear_fecha(inp_fecha_inicio.value)
        hasta = parsear_fecha(inp_fecha_fin.value)
        if desde and hasta and desde > hasta:
            txt_error_fecha.value = "La fecha inicio no puede ser mayor que la fecha fin."
            await page.update_async()
            return
        await construir_lista_pedidos(filtrar_pedidos(_todos_los_pedidos))
        await page.update_async()

    async def ejecutar_reporte_pdf(e):
        txt_error_fecha.value = "⏳ Generando reporte..."
        await page.update_async()
        try:
            from reports import generar_pdf_pedidos
            # Usamos los pedidos que están cargados actualmente
            pedidos_para_pdf = filtrar_pedidos(_todos_los_pedidos)
            
            if not pedidos_para_pdf:
                txt_error_fecha.value = "⚠️ No hay pedidos en este rango."
                await page.update_async()
                return

            rango = f"{inp_fecha_inicio.value} a {inp_fecha_fin.value}" if inp_fecha_inicio.value else "General"
            nombre_archivo = generar_pdf_pedidos(pedidos_para_pdf, rango)
            
            # Abrir el PDF en una nueva pestaña (localhost:8000 es la API)
            await page.launch_url_async(f"http://localhost:8000/static/{nombre_archivo}")
            txt_error_fecha.value = "✅ Reporte generado."
        except Exception as ex:
            txt_error_fecha.value = f"❌ Error PDF: {ex}"
        await page.update_async()
        
    btn_reporte = ft.ElevatedButton(
        "Generar PDF", 
        icon="picture_as_pdf", 
        bgcolor="#c62828", 
        color="white",
        on_click=ejecutar_reporte_pdf
    )

    async def limpiar_filtro(e=None):
        inp_fecha_inicio.value = inp_fecha_fin.value = txt_error_fecha.value = ""
        await construir_lista_pedidos(_todos_los_pedidos)
        await page.update_async()

    # ─── MODAL SUMINISTRO ─────────────────────────────────────
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
        id_actual.value = str(pid)
        input_stock.value = "10"
        modal.open = True
        await page.update_async()

    # ─── MODAL NUEVO PRODUCTO ─────────────────────────────────
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
                db, nombre=inp_nombre.value.strip(), marca=inp_marca.value.strip(),
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

    async def abrir_crear(e=None):
        modal_crear.open = True
        await page.update_async()

    modal_crear = ft.AlertDialog(
        title=ft.Text("Nuevo Producto"),
        content=ft.Column([
            inp_nombre, inp_marca,
            ft.Row([inp_precio, inp_costo], spacing=10),
            ft.Row([inp_stock_nuevo, inp_minimo], spacing=10),
            txt_error_prod,
        ], spacing=10, tight=True, width=310),
        actions=[
            ft.TextButton("Cancelar", on_click=cerrar_crear),
            ft.ElevatedButton("Crear", on_click=guardar_nuevo_producto,
                              bgcolor="green", color="white"),
        ],
    )
    page.overlay.append(modal_crear)

    # ─── MODAL ELIMINAR PRODUCTO ──────────────────────────────
    id_a_eliminar    = ft.Text("", visible=False)
    txt_msg_eliminar = ft.Text("", size=14)

    async def confirmar_eliminar(e):
        resultado = await run_db(
            lambda db: crud.eliminar_producto(db, int(id_a_eliminar.value))
        )
        modal_eliminar.open = False
        msg   = ("Marcado como DESCONTINUADO" if resultado == "descontinuado"
                 else "Producto eliminado correctamente")
        color = "orange" if resultado == "descontinuado" else "green"
        snack = ft.SnackBar(ft.Text(msg), bgcolor=color)
        page.overlay.append(snack)
        snack.open = True
        await refrescar_datos()

    async def cerrar_eliminar(e=None):
        modal_eliminar.open = False
        await page.update_async()

    async def abrir_eliminar(pid: int, nombre: str):
        id_a_eliminar.value    = str(pid)
        txt_msg_eliminar.value = (
            f'¿Eliminar "{nombre}"?\n\n'
            "Si tiene pedidos vinculados se marcara como DESCONTINUADO."
        )
        modal_eliminar.open = True
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

    # ─── MODAL EDITAR PEDIDO ──────────────────────────────────
    col_items_editar   = ft.Column(spacing=8, scroll="always", height=300)
    txt_total_editar   = ft.Text("Total: S/ 0.00", size=16, weight="bold", color="amber")
    txt_error_editar   = ft.Text("", color="red", size=12)
    _pedido_id_editar  = {"id": None}
    _productos_cache   = []

    # Dropdown para agregar nuevo producto
    dd_nuevo_prod = ft.Dropdown(
        label="Agregar producto", width=220,
        options=[], bgcolor="#0b0d0f", color="white",
    )
    inp_nueva_cantidad = ft.TextField(label="Cantidad", width=90, value="1")

    async def cargar_modal_editar(pedido_id: int):
        """Carga el pedido y construye las filas editables."""
        _pedido_id_editar["id"] = pedido_id
        txt_error_editar.value  = ""

        pedido = await run_db(lambda db: crud.obtener_pedido_con_items(db, pedido_id))
        prods  = await run_db(lambda db: db.query(models.Producto).all())
        _productos_cache.clear()
        _productos_cache.extend(prods)

        # Actualizar dropdown de productos disponibles
        dd_nuevo_prod.options = [
            ft.dropdown.Option(key=str(p.id), text=f"{p.nombre} (S/{p.precio_venta or 0:.2f})")
            for p in prods if not p.nombre.startswith("[DESCONTINUADO]")
        ]
        dd_nuevo_prod.value = None

        # Construir filas de items editables
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
                                ft.Text(f"S/ {precio_unit:.2f} c/u  →  subtotal S/ {subtotal:.2f}",
                                        size=11, color="#aaa"),
                            ], expand=True, spacing=1),
                            inp_cant,
                            ft.IconButton(icon="check_circle", icon_color="green",
                                          icon_size=20, tooltip="Guardar cantidad",
                                          on_click=guardar_cantidad),
                            ft.IconButton(icon="remove_circle", icon_color="red",
                                          icon_size=20, tooltip="Quitar item",
                                          on_click=quitar_item),
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
                ft.ElevatedButton("Agregar", bgcolor="#1565c0", color="white",
                                  on_click=agregar_nuevo_item),
            ], spacing=8, vertical_alignment="center"),
            txt_error_editar,
        ], spacing=10, tight=True, width=480),
        actions=[
            ft.ElevatedButton("Cerrar y guardar", on_click=cerrar_editar,
                              bgcolor="green", color="white"),
        ],
    )
    page.overlay.append(modal_editar)

    # ─── CAMBIO DE ESTADO ─────────────────────────────────────
    async def cambiar_estado(pedido_id: int, nuevo_estado: str):
        await run_db(lambda db: crud.actualizar_estado_pedido(db, pedido_id, nuevo_estado))
        peds = await run_db(lambda db: db.query(models.Pedido).all())
        ventas = sum(p.total_pedido for p in peds if p.total_pedido)
        txt_ventas.value  = f"S/ {ventas:,.2f}"
        txt_pedidos.value = str(len(peds))
        await page.update_async()

    # ─── CONSTRUIR LISTA DE PEDIDOS ───────────────────────────
    async def construir_lista_pedidos(peds):
        lista_pedidos_ui.controls.clear()
        if not peds:
            lista_pedidos_ui.controls.append(ft.Container(
                content=ft.Text("No hay pedidos en ese rango de fechas.",
                                color="grey", italic=True),
                padding=20,
            ))
            return

        for p in peds:
            nombre_cliente = p.cliente.nombre_completo if p.cliente else "Anonimo"
            total          = p.total_pedido or 0.0
            estado_actual  = p.estado_logistico or "recibido"
            color_estado   = COLORES_ESTADO.get(estado_actual, "grey")

            fecha_str = ""
            if p.fecha_hora:
                fh = p.fecha_hora if isinstance(p.fecha_hora, datetime) else datetime.fromisoformat(str(p.fecha_hora))
                fecha_str = fh.strftime("%d/%m/%Y %H:%M")

            filas_items = []
            if p.items:
                for item in p.items:
                    nombre_prod = item.producto.nombre if item.producto else "Eliminado"
                    precio_unit = (item.producto.precio_venta or 0) if item.producto else 0
                    subtotal    = precio_unit * (item.cantidad or 0)
                    filas_items.append(ft.Row(controls=[
                        ft.Icon("circle", size=7, color="amber"),
                        ft.Text(nombre_prod, expand=True, size=13),
                        ft.Text(f"x{item.cantidad}", width=40, size=13,
                                color="grey", text_align="right"),
                        ft.Text(f"S/ {subtotal:.2f}", width=75, size=13,
                                color="amber", text_align="right"),
                    ], spacing=8, vertical_alignment="center"))
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
                            ft.Row([
                                ft.Text(f"Pedido #{p.id}  —  {nombre_cliente}",
                                        weight="bold", size=14),
                                ft.Text(fecha_str, color="#555", size=11),
                            ], spacing=10),
                            ft.Row(controls=[
                                ft.Text(f"S/ {total:.2f}", color="amber", size=13),
                                dropdown_estado,
                            ], spacing=10, vertical_alignment="center"),
                        ], expand=True, spacing=4),
                        # Boton editar pedido
                        ft.IconButton(
                            icon="edit_note", icon_color="#1565c0",
                            icon_size=22, tooltip="Editar pedido",
                            on_click=lambda e, pid=p.id: asyncio.ensure_future(
                                cargar_modal_editar(pid)
                            ),
                        ),
                        btn_expand,
                    ], vertical_alignment="center", spacing=12),
                    panel_detalle,
                ], spacing=0),
                bgcolor="#16191c", border_radius=10,
                padding=ft.padding.symmetric(horizontal=14, vertical=10),
            ))

    # ─── REFRESCO PRINCIPAL ───────────────────────────────────
    async def refrescar_datos(e=None):
        nonlocal _todos_los_pedidos
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

            _todos_los_pedidos = peds

            criticos = [p for p in prods if (p.stock_actual or 0) <= (p.stock_minimo or 10)]
            txt_alertas.value = str(len(criticos))
            txt_pedidos.value = str(len(peds))
            ventas = sum(p.total_pedido for p in peds if p.total_pedido)
            txt_ventas.value  = f"S/ {ventas:,.2f}"

            await construir_lista_pedidos(filtrar_pedidos(peds))

            lista_inventario_ui.controls.clear()
            for pr in prods:
                es_bajo = (pr.stock_actual or 0) <= (pr.stock_minimo or 10)
                es_desc = pr.nombre.startswith("[DESCONTINUADO]")
                
                lista_inventario_ui.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(pr.nombre, weight="bold", color="#666" if es_desc else "white"),
                            ft.Row([
                                ft.Text("Stock disponible:", color="#aaa", size=12),
                                ft.Text(
                                    f"{pr.stock_actual}", 
                                    color="red" if es_bajo else "green", 
                                    weight="bold", 
                                    size=15
                                ),
                                ft.Container(
                                    visible=es_bajo and not es_desc,
                                    content=ft.Text("STOCK BAJO", size=9, weight="bold"),
                                    bgcolor="red", border_radius=4, padding=3
                                ),
                            ], spacing=8),
                        ], expand=True, spacing=2),
                        ft.IconButton(
                            icon="add_circle", icon_color="green", icon_size=22,
                            tooltip="Sumar stock", visible=not es_desc,
                            on_click=lambda e, pid=pr.id: asyncio.ensure_future(abrir_suministro(pid)),
                        ),
                        ft.IconButton(
                            icon="delete_outline", icon_color="red", icon_size=22,
                            tooltip="Eliminar producto",
                            on_click=lambda e, pid=pr.id, nom=pr.nombre: asyncio.ensure_future(abrir_eliminar(pid, nom)),
                        ),
                    ], vertical_alignment="center"),
                    padding=10, bgcolor="#16191c", border_radius=10,
                    border=ft.border.all(1, "red") if es_bajo else None
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
                ft.Row([
                    inp_fecha_inicio, inp_fecha_fin,
                    ft.ElevatedButton("Filtrar", bgcolor="#1565c0", color="white",
                                      height=40, on_click=aplicar_filtro),btn_reporte,
                    ft.TextButton("Limpiar", on_click=limpiar_filtro),
                ], spacing=8, vertical_alignment="center"),
                txt_error_fecha,
                ft.Container(content=lista_pedidos_ui, height=400),
            ], expand=2),

            ft.Column([
                ft.Row([
                    ft.Text("Inventario", size=18, weight="bold", expand=True),
                    ft.ElevatedButton("+ Nuevo", bgcolor="green", color="white",
                                      height=32,
                                      on_click=lambda e: asyncio.ensure_future(abrir_crear())),
                ], vertical_alignment="center"),
                ft.Container(content=lista_inventario_ui, height=450),
            ], expand=1),
        ], vertical_alignment="start", spacing=30),
    )

    await refrescar_datos()