FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port viene assegnata da Render
ENV PORT=8877
ENV PYTHONIOENCODING=utf-8

EXPOSE 8877

CMD ["python", "app.py"]
