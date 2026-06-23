FROM python:3.11-slim

# Install system dependencies (tesseract + poppler for pdf2image)
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       tesseract-ocr \
       poppler-utils \
       build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY poc /app/poc
COPY examples /app/examples
COPY README.md /app/README.md
COPY ui /app/ui

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "poc.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
