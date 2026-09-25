FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY . .
RUN mkdir -p data
CMD ["python", "-m", "app.main"]
