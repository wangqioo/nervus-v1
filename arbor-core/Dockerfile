FROM nervus-python-base:latest

WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

EXPOSE 8090

CMD ["python", "main.py"]
