FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir flask paho-mqtt
COPY app.py .
EXPOSE 5001
CMD ["python", "app.py"]
