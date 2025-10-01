# Paso 1: Usar una imagen oficial de Python como base.
# La versión 3.9 es estable y compatible con todas tus librerías.
FROM python:3.9-slim

# Paso 2: Establecer el directorio de trabajo dentro del contenedor.
WORKDIR /app

# Paso 3: Instalar las dependencias del sistema operativo.
# Aquí está la magia: instalamos 'portaudio19-dev' que 'pyaudio' necesita.
# 'build-essential' incluye herramientas para compilar.
# '--no-install-recommends' hace la instalación más ligera.
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Paso 4: Copiar el archivo de requisitos de Python primero.
# Esto aprovecha el caché de Docker para acelerar futuras construcciones.
COPY requirements.txt .

# Paso 5: Instalar las librerías de Python.
RUN pip install --no-cache-dir -r requirements.txt

# Paso 6: Copiar el resto del código de tu aplicación al contenedor.
COPY . .

# Paso 7: Exponer el puerto que Render usará.
# Render asignará un puerto dinámicamente, pero es buena práctica declararlo.
EXPOSE 10000

# Paso 8: El comando final para ejecutar tu servidor cuando el contenedor se inicie.
CMD ["python", "idioma_server.py"]
