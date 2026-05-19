# 1. Imagen base estable
FROM python:3.10-slim

# 2. Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /usr/src/bot

# 4. Dependencias del sistema (optimizadas en una sola capa)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Instalación de librerías (Usando caché de capas)
# Solo se volverá a ejecutar si cambias el requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install python-multipart 


# 6. Copiar todo el contenido de la carpeta raiz al contenedor
COPY . .  

# 7. Exponer los puertos: 8502 para la Web (Flet) y 8000 para la API
#EXPOSE 8502
EXPOSE 8000

# 8. Comando para arrancar la aplicación
CMD ["python", "-m", "app.main"]
