# Build context è la root del progetto (docker-compose: context: .)
# così possiamo copiare il pacchetto faceid esistente.
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    g++ \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    opencv-python-headless \
    insightface \
    onnxruntime \
    faiss-cpu \
    numpy \
    paho-mqtt

# Copia il pacchetto faceid dal progetto root e installalo
COPY faceid/ ./faceid/
COPY setup.py .
RUN pip install --no-cache-dir -e .

# Copia il servizio
COPY face-recognition-service/app.py ./app.py

CMD ["python", "app.py"]
