FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml ./
# Default build installs only the portable backend. For the NAS, build with
# openvino by adding it to the install target (see pyproject [openvino]).
RUN pip install --upgrade pip && pip install .

COPY . .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
