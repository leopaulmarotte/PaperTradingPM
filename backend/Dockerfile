FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run with app.main:app (proper package structure)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
