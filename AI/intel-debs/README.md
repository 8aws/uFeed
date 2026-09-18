# Intel GPU/NPU user-space runtime (.deb) for the OpenVINO image

Brand-new Intel silicon (e.g. **Wildcat Lake**, Core Series 3) is not recognised
by the Intel runtime that ships in Debian/Ubuntu `apt` — the packages there are
too old to know the new device IDs. That is exactly why OpenVINO inside the
container sees only `CPU` even though the host kernel already drives the iGPU/NPU.

Drop the **matched** Intel `.deb` files here and rebuild the OpenVINO image; the
Dockerfile installs any `*.deb` in this directory (and falls back to the apt
baseline only if this directory is empty).

## Wildcat Lake verified stack (from Intel docs, mid-2026)

| Component                         | Version              | Source (GitHub releases) |
|-----------------------------------|----------------------|--------------------------|
| OpenVINO                          | 2026.2               | installed via pip (pyproject) |
| Compute Runtime (GPU / NEO)       | 26.22.38646.6        | `intel/compute-runtime` |
| Level Zero loader                 | 1.28.2               | `oneapi-src/level-zero` |
| Intel Graphics Compiler (IGC)     | matched to NEO release | `intel/intel-graphics-compiler` |
| NPU driver (host + container)     | 1.35.0+ (1.38.x rc)  | `intel/linux-npu-driver` |

Check the current recommendation at:
https://docs.openvino.ai/systemrequirements  and the release pages above.

## What to download here (iGPU)

From the `intel/compute-runtime` release `26.22.38646.6` (and its matched IGC
release), the amd64 `.deb`s, typically:

- `intel-opencl-icd_*_amd64.deb`
- `libze-intel-gpu1_*_amd64.deb`  (a.k.a. intel-level-zero-gpu)
- `libigdgmm12_*_amd64.deb`
- `intel-igc-core*_*_amd64.deb` and `intel-igc-opencl*_*_amd64.deb`
- the Level Zero loader `.deb` from `oneapi-src/level-zero` `v1.28.2`

## What to download here (NPU, optional)

From `intel/linux-npu-driver` release `1.35.0` (or newer) the amd64 `.deb`s:

- `intel-driver-compiler-npu_*_amd64.deb`
- `intel-fw-npu_*_amd64.deb`
- `intel-level-zero-npu_*_amd64.deb`

Also install the matching Level Zero loader on the **host** and pass
`/dev/accel/accel0` (see `compose.openvino.yml`).

> Keep this directory in git via `.keep`; do **not** commit the large `.deb`
> binaries — they are box-specific and version-specific.
