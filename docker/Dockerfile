# 1. Usamos una imagen de Python oficial y ligera
FROM python:3.10-slim

# 2. Evitamos que Python genere archivos .pyc y que el buffer se sature
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. Directorio de trabajo dentro del contenedor
WORKDIR /usr/src/bot

# 4. Instalar dependencias del sistema necesarias para PostgreSQL y compilación
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 5. Copiar el archivo de requerimientos e instalar las bibliotecas
# Hacemos esto antes de copiar el código para aprovechar el "cache" de Docker
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