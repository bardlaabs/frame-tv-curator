FROM python:3.12-slim
RUN pip install --no-cache-dir pillow pillow-heif numpy samsungtvws paho-mqtt websocket-client requests
WORKDIR /app
COPY curator /app/curator
ENV PYTHONUNBUFFERED=1 FC_MEDIA=/media FC_DATA=/data
CMD ["python", "-m", "curator"]
