FROM python:3.11-slim

WORKDIR /app

RUN pip install fastapi uvicorn[standard] requests

COPY tts_common /app/tts_common
COPY tts_gateway/app.py /app/app.py

EXPOSE 9000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000"]
