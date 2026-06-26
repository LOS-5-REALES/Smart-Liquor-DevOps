# app/reports.py
"""
Módulo de generación de reportes.

Utiliza la librería ReportLab para construir documentos PDF dinámicos
a partir de los datos extraídos de la base de datos.
"""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime


def generar_pdf_pedidos(pedidos: list, rango_fechas: str = "Todas") -> str:
    """
    Genera un archivo PDF con formato tabular mostrando el listado de pedidos.

    Crea automáticamente una carpeta `static/` si no existe, donde guardará
    el archivo generado. El nombre del archivo es único, basado en la fecha
    y hora exacta de generación.

    Args:
        pedidos (list): Lista de objetos `models.Pedido` (generalmente ya filtrados)
                        que se incluirán en el reporte.
        rango_fechas (str, optional): Texto descriptivo del filtro aplicado que
                                      aparecerá en el encabezado del PDF.
                                      Por defecto es "Todas".

    Returns:
        str: El nombre exacto del archivo PDF generado (ej. "reporte_pedidos_20260521_153000.pdf").
             No devuelve la ruta completa, solo el nombre del archivo.
    """
    # Carpeta temporal para guardar el PDF antes de mostrarlo
    if not os.path.exists("static"):
        os.makedirs("static")

    filename = f"reporte_pedidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join("static", filename)

    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    elementos = []

    # Título y encabezado
    elementos.append(Paragraph("Reporte de Pedidos - Smart Liquor", styles['Title']))
    elementos.append(Paragraph(f"Filtro: {rango_fechas}", styles['Normal']))
    elementos.append(Paragraph(f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
    elementos.append(Spacer(1, 20))

    # Datos para la tabla
    data = [["ID", "Cliente", "Fecha", "Total", "Estado"]]
    for p in pedidos:
        fecha = p.fecha_hora.strftime('%d/%m/%Y') if p.fecha_hora else "S/F"
        nombre = p.cliente.nombre_completo if p.cliente else "Anonimo"
        data.append([str(p.id), nombre, fecha, f"S/ {p.total_pedido:.2f}", p.estado_logistico.upper()])

    # Estilo de la tabla
    t = Table(data, colWidths=[30, 180, 80, 80, 100])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elementos.append(t)
    doc.build(elementos)
    return filename