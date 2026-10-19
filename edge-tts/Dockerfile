FROM python:3.11-slim

WORKDIR /app

RUN pip install fastapi uvicorn[standard] requests edge-tts

COPY tts_common /app/tts_common
COPY edge-tts/app.py /app/app.py
COPY edge-tts/tts_client.py /app/tts_client.py
COPY edge-tts/test_api.py /app/test_api.py

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
