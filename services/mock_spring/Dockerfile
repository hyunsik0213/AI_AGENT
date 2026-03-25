FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY services/mock_spring /app/services/mock_spring
COPY data /app/data

ENV PYTHONUNBUFFERED=1
EXPOSE 8001
CMD ["uvicorn", "services.mock_spring.main:app", "--host", "0.0.0.0", "--port", "8001"]
