FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock
COPY app.py .
ENV PORT=8787
EXPOSE 8787
CMD ["python", "app.py"]
