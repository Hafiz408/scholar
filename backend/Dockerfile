FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# Clone the PageIndex open-source library (no pyproject.toml — install via PYTHONPATH).
RUN git clone --depth=1 https://github.com/VectifyAI/PageIndex.git /opt/pageindex
ENV PYTHONPATH="/opt/pageindex:${PYTHONPATH}"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
