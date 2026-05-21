# Actualizamos a la versión v1.59.0 que piden los logs
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# Copiamos los requerimientos e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Exponemos el puerto de Hugging Face
EXPOSE 7860

# Comando de arranque
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
