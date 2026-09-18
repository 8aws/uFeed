FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Default build installs only the portable backend. Prod (NAS) builds with
#   --build-arg AI_EXTRAS="[openvino]"
# to pull OpenVINO + optimum-intel for Intel iGPU/NPU inference.
ARG AI_EXTRAS=""

# For the OpenVINO variant (AI_EXTRAS="[openvino]") install the Intel user-space
# GPU runtime INSIDE the image. This is the piece most often missing: the host's
# drivers do not reach the container. OpenVINO's GPU plugin loads through Level
# Zero / OpenCL, both of which are user-space libraries that must live here for
# /dev/dri to be usable. The default (hashing) build installs none of this, so
# the portable image and CI stay apt-free.
#   iGPU: handled below (Level Zero loader + Intel L0 GPU driver + OpenCL ICD).
#   NPU:  additionally needs Intel's linux-npu-driver .debs (not in apt, kernel-
#         version-matched) and /dev/accel passed in — see compose.openvino.yml.
RUN if [ "${AI_EXTRAS}" = "[openvino]" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            intel-opencl-icd \
            libze1 \
            libze-intel-gpu1 \
            ocl-icd-libopencl1 \
            clinfo && \
        rm -rf /var/lib/apt/lists/*; \
    fi

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".${AI_EXTRAS}"

COPY . .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
