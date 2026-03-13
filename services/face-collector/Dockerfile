FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir paho-mqtt

COPY face-collector/app.py face-collector/db.py ./

CMD ["python", "app.py"]
