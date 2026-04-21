FROM nervus-python-base:latest
WORKDIR /app
COPY nervus-sdk /app/nervus-sdk
COPY apps/sense/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && pip install --no-cache-dir /app/nervus-sdk -i https://pypi.tuna.tsinghua.edu.cn/simple
COPY apps/sense/. .
RUN mkdir -p /app/frontend
EXPOSE 8005
CMD ["python", "main.py"]
