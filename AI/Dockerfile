FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Default build installs only the portable backend. Prod (NAS) builds with
#   --build-arg AI_EXTRAS="[openvino]"
# to pull OpenVINO + optimum-intel for Intel iGPU/NPU inference.
ARG AI_EXTRAS=""

# For the OpenVINO variant (AI_EXTRAS="[openvino]") the Intel user-space GPU/NPU
# runtime must live INSIDE the image. This is the piece most often missing: the
# host's drivers do not reach the container. OpenVINO's GPU/NPU plugins load
# through Level Zero / OpenCL, user-space libraries that must be present here for
# /dev/dri (iGPU) and /dev/accel (NPU) to be usable. The default (hashing) build
# installs none of this, so the portable image and CI stay apt-free.
#
# Brand-new silicon (e.g. Wildcat Lake / Core Series 3) is NOT recognised by the
# runtime in Debian/Ubuntu apt — those packages are too old for the new device
# IDs, so the container falls back to CPU. For such boxes, drop the matched Intel
# .deb files into AI/intel-debs/ (see its README for the exact versions) and they
# are installed below. If that directory has no .deb, we fall back to the apt
# baseline, which is fine only for hardware already supported by the distro.
COPY intel-debs/ /tmp/intel-debs/
RUN if [ "${AI_EXTRAS}" = "[openvino]" ]; then \
        apt-get update; \
        if ls /tmp/intel-debs/*.deb >/dev/null 2>&1; then \
            apt-get install -y --no-install-recommends ocl-icd-libopencl1 clinfo && \
            (dpkg -i /tmp/intel-debs/*.deb || apt-get install -y -f --no-install-recommends); \
        else \
            echo "intel-debs/ empty -> apt baseline runtime (too old for newest silicon)"; \
            apt-get install -y --no-install-recommends \
                intel-opencl-icd libze1 libze-intel-gpu1 ocl-icd-libopencl1 clinfo; \
        fi; \
        rm -rf /var/lib/apt/lists/* /tmp/intel-debs; \
    fi

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".${AI_EXTRAS}"

COPY . .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
