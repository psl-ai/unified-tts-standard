FROM docker.1ms.run/python:3.11-slim
WORKDIR /app

RUN pip install fastapi uvicorn[standard] requests

COPY tts_common /app/tts_common
COPY tianyi_tts/app.py /app/app.py
COPY tianyi_tts/test_api.py /app/test_api.py
COPY tianyi_tts/tts_client.py /app/tts_client.py

EXPOSE 8900

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8900"]
