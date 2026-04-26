FROM python:3.11-slim
WORKDIR /app
COPY sdk/python /app/nervus-sdk
COPY apps/model-manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir /app/nervus-sdk
COPY apps/model-manager/manifest.json /app/manifest.json
COPY apps/model-manager/main.py .
COPY apps/model-manager/index.html .
EXPOSE 8016
CMD ["python", "main.py"]
