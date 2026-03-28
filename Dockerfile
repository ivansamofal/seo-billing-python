FROM python:3.12-slim

WORKDIR /app

RUN addgroup --gid 1001 billing && \
    adduser --uid 1001 --gid 1001 --no-create-home --disabled-password billing

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chown -R billing:billing /app
USER billing

CMD ["python", "-m", "src.main", "update-balance"]
