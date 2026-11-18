FROM docker:27-cli AS dockercli
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
