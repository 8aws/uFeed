FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Default build installs only the portable backend. Prod (NAS) builds with
#   --build-arg AI_EXTRAS="[openvino]"
# to pull OpenVINO + optimum-intel for Intel iGPU/NPU inference.
ARG AI_EXTRAS=""
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".${AI_EXTRAS}"

COPY . .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
