FROM nervus-python-base:latest
WORKDIR /app
COPY nervus-sdk /app/nervus-sdk
COPY apps/meeting-notes/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY apps/meeting-notes/. .
RUN mkdir -p /data
EXPOSE 8002
CMD ["python", "main.py"]
