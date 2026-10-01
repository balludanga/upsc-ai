FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

# rapidocr pulls in opencv-python, which needs the heavyweight GL/Mesa
# system libraries. rapidocr only uses cv2 for headless image work, so
# swap it for the headless build and keep the image small.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y opencv-python \
    && pip install --no-cache-dir opencv-python-headless

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
