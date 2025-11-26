FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.0

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

COPY . .

RUN poetry install --no-interaction --no-ansi

EXPOSE 8501

ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

CMD ["streamlit", "run", "src/vendor_ai_agent/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
