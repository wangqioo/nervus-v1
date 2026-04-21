FROM nervus-python-base:latest
WORKDIR /app
COPY nervus-sdk /app/nervus-sdk
COPY apps/life-memory/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY apps/life-memory/. .
RUN mkdir -p /data
EXPOSE 8004
CMD ["python", "main.py"]
