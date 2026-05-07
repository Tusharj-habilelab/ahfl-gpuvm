First, your English corrected and tightened version of the request:

> “Please check the `day6-07052026-1.md` file. It contains logs from the GPU server. I was mainly facing issues related to CUDA libraries, CUDA indexing, and PaddleOCR versions. Previously, I ran another container using the same versions and libraries, but I still encountered issues. Please review the Day 6 steps, compare both Dockerfiles and requirements files from the two services, and tell me the actual root cause and solution.”

Now the actual technical analysis.

---

# Main Finding

Your issue is  **NOT primarily CUDA itself** .

The real issue is:

1. **Duplicate installation of GPU frameworks**
2. **Version collision between Dockerfile-installed packages and requirements-installed packages**
3. **Improper dependency ownership**
4. **Potential ABI/runtime mismatch between CUDA 12.2 container and cu121 wheels**
5. **PaddleOCR 3.4.0 + PaddlePaddle 3.3.0 GPU stack instability**
6. **Container dependency pollution from pip reinstall order**

---

# The Biggest Problem

Both Dockerfiles already install:

* `paddlepaddle-gpu==3.3.0`
* `torch==2.1.2+cu121`
* `torchvision==0.16.2+cu121`

But then your requirements file again contains:

* `paddlepaddle-gpu==3.3.0`
* `torch==2.1.2+cu121`
* `torchvision==0.16.2+cu121`

From:

* `requirements.txt`
* `requirements(1).txt`

That is architecturally wrong.

---

# Why This Breaks

You install GPU wheels manually using:

```dockerfile
RUN pip install paddlepaddle-gpu==3.3.0 \
-i https://www.paddlepaddle.org.cn/packages/stable/cu121/
```

Then later:

```dockerfile
RUN pip install -r requirements.txt
```

Now pip tries dependency resolution again.

This can:

* reinstall packages
* downgrade transitive deps
* pull CPU-compatible subpackages
* replace CUDA-linked libs
* overwrite protobuf/opencv/numpy bindings
* break Paddle native bindings

This is extremely common with Paddle + Torch mixed containers.

---

# Another Critical Problem

Your base image:

```dockerfile
FROM nvidia/cuda:12.2.2-cudnn8-runtime-ubuntu22.04
```

But:

* Torch wheels are `cu121`
* Paddle wheel index is `cu121`

That *usually* works because CUDA 12.2 runtime is ABI compatible with 12.1 wheels.

BUT…

Paddle is much more fragile than PyTorch regarding:

* cuDNN
* TensorRT
* libcublas
* NCCL
* runtime symbol resolution

PyTorch tolerates mismatch better.

Paddle often does not.

---

# Your Logs Confirm Important Context

Your server has:

* NVIDIA Driver: `580.126.16`
* CUDA Driver Capability: `13.0`
* GPU: Tesla T4

From the log file:

This means:

* Driver side is modern enough
* Hardware is fine
* The issue is container runtime compatibility and Python dependency stack

NOT GPU hardware.

---

# The REAL Root Cause

The strongest probability:

## You created a partially inconsistent Python environment.

Specifically:

### Service A

Installs GPU packages BOTH:

* in Dockerfile
* in requirements

### Service B

Partially avoids this by commenting Torch in requirements.

This difference matters.

---

# Correct Architecture

GPU frameworks should NEVER be inside requirements.txt.

They should ONLY exist in Dockerfile.

Reason:

GPU wheels depend on:

* CUDA version
* cuDNN version
* architecture
* NVIDIA runtime
* wheel index

Those are infrastructure concerns, not Python dependency concerns.

---

# What You Should Change

# FIX 1 — Remove GPU Packages From Requirements

Remove these from ALL requirements files:

```txt
paddlepaddle-gpu==3.3.0
torch==2.1.2+cu121
torchvision==0.16.2+cu121
```

Keep ONLY:

```txt
paddleocr==3.4.0
ultralytics==8.3.235
```

This is the most important fix.

---

# FIX 2 — Use ONE Source of Truth

GPU framework installs should ONLY happen in Dockerfile.

Correct:

```dockerfile
RUN pip install --no-cache-dir \
    paddlepaddle-gpu==3.3.0 \
    -i https://www.paddlepaddle.org.cn/packages/stable/cu121/

RUN pip install --no-cache-dir \
    torch==2.1.2+cu121 \
    torchvision==0.16.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121
```

Then requirements should contain only application-level deps.

---

# FIX 3 — Install PaddleOCR AFTER Paddle

Correct order:

1. paddlepaddle-gpu
2. torch
3. torchvision
4. paddleocr
5. ultralytics
6. rest

Because PaddleOCR imports Paddle internals during installation/runtime.

---

# FIX 4 — Pin protobuf

Paddle + OCR stacks frequently break on protobuf.

Add:

```txt
protobuf==3.20.3
```

This prevents random runtime crashes/import failures.

---

# FIX 5 — Pin ONNX Carefully

You use:

```txt
onnxruntime-gpu==1.17.0
```

That package itself may introduce CUDA runtime conflicts.

Especially with:

* cuDNN
* libcublas
* CUDA execution providers

If ONNX is not mandatory:

REMOVE IT.

Seriously.

---

# FIX 6 — Add Runtime Validation Layer

After installs, add this to Dockerfile:

```dockerfile
RUN python -c "import paddle; print(paddle.device.get_device())"
RUN python -c "import torch; print(torch.cuda.is_available())"
RUN python -c "from paddleocr import PaddleOCR; print('OCR OK')"
```

This catches broken layers during build time instead of runtime.

---

# FIX 7 — Your Container Is Missing NVIDIA Runtime Validation

Run container with:

```bash
docker run --gpus all
```

Or in compose:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Otherwise CUDA libraries won't mount correctly.

---

# Most Likely Failure Chain

This is probably what happened:

```text
Docker installs correct GPU wheel
        ↓
requirements.txt reinstalls conflicting deps
        ↓
CUDA-linked native bindings mismatch
        ↓
PaddleOCR fails internally
        ↓
CUDA indexing / libcudnn / kernel errors appear
```

---

# Your Clean Final Architecture

## Dockerfile

Install:

* paddlepaddle-gpu
* torch
* torchvision

ONLY HERE.

---

## requirements.txt

Keep ONLY:

```txt
fastapi
uvicorn
paddleocr
ultralytics
opencv-python-headless
numpy
Pillow
pdf2image
PyPDF2
pytesseract
protobuf==3.20.3
```

No GPU wheels.

---

# Another Very Important Thing

Your log file exposes a GitHub Personal Access Token publicly:

```text
github_pat_...
```

Inside `git remote -v`.

That is a severe security issue.

Immediately:

1. Revoke the token
2. Generate new token
3. Use SSH auth instead
4. Never store PAT in remote URL

That is production-critical.

---

# My Technical Recommendation

Your stack is becoming too dependency-heavy:

* Paddle
* Torch
* ONNX
* OCR
* YOLO
* CUDA
* cuDNN

inside one container.

That becomes fragile quickly.

The cleaner architecture is:

## Option A — Best

Separate services:

* OCR Service (Paddle only)
* Detection Service (Torch/YOLO only)

This reduces CUDA conflicts massively.

---

## Option B — Acceptable

Single container but:

* no duplicate installs
* no ONNX unless needed
* strict version pinning
* build-time validation

---

# Final Conclusion

Your issue is NOT:

* GPU hardware
* NVIDIA driver
* CUDA installation on host

Your issue is primarily:

## Dependency collision + GPU wheel duplication + runtime ABI inconsistency.

That is the real root cause.





# Detailed Comparison Table — Both Services

## 1. Requirements Files Comparison

| Category             | Library                | Service A —`requirements.txt` | Service B —`requirements(1).txt` | Notes / Nuance              |
| -------------------- | ---------------------- | -------------------------------- | ----------------------------------- | --------------------------- |
| Environment          | python-dotenv          | `1.0.1`                        | `1.0.1`                           | Same                        |
| Upload Handling      | python-multipart       | `0.0.9`                        | `0.0.9`                           | Same                        |
| Validation           | pydantic               | `2.7.0`                        | `2.7.0`                           | Same                        |
| Validation Config    | pydantic-settings      | ❌                               | `2.2.0`                           | Only in Service B           |
| API Framework        | fastapi                | ❌                               | `0.115.0`                         | Only API service            |
| API Server           | uvicorn[standard]      | ❌                               | `0.30.6`                          | Only API service            |
| Paddle GPU Framework | paddlepaddle-gpu       | `3.3.0`                        | Mentioned in comments only          | Important difference        |
| OCR Engine           | paddleocr              | `3.4.0`                        | `3.4.0`                           | Same                        |
| YOLO Framework       | ultralytics            | `8.3.235`                      | `8.3.235`                         | Same                        |
| Torch GPU Framework  | torch                  | `2.1.2+cu121`                  | Commented out                       | Docker-managed in Service B |
| Torch Vision         | torchvision            | `0.16.2+cu121`                 | Commented out                       | Docker-managed in Service B |
| OpenCV               | opencv-python-headless | `4.9.0.80`                     | `4.9.0.80`                        | Same                        |
| Numerical Computing  | numpy                  | `1.26.4`                       | `1.26.4`                          | Same                        |
| Image Processing     | Pillow                 | `10.4.0`                       | `10.4.0`                          | Same                        |
| ONNX Core            | onnx                   | ❌                               | `1.15.0`                          | Only in Service B           |
| ONNX GPU Runtime     | onnxruntime-gpu        | ❌                               | `1.17.0`                          | Important CUDA nuance       |
| PDF Handling         | pdf2image              | `1.17.0`                       | `1.17.0`                          | Same                        |
| PDF Handling         | img2pdf                | `0.5.1`                        | `0.5.1`                           | Same                        |
| PDF Handling         | PyPDF2                 | `3.0.1`                        | `3.0.1`                           | Same                        |
| Archive Extraction   | patool                 | `3.1.3`                        | ❌                                  | Only in Service A           |
| OCR Fallback         | pytesseract            | `0.3.13`                       | `0.3.13`                          | Same                        |
| AWS SDK              | boto3                  | `>=1.34.0`                     | ❌                                  | Only in Service A           |
| Logging              | python-json-logger     | ❌                               | `2.0.7`                           | Only in Service B           |
| Monitoring           | psutil                 | ❌                               | `5.9.8`                           | Only in Service B           |

Sources:

* `requirements.txt`
* `requirements(1).txt`

---

# 2. CUDA / GPU Dependency Comparison

| GPU Layer               | Service A      | Service B             | Risk Level  | Notes                      |
| ----------------------- | -------------- | --------------------- | ----------- | -------------------------- |
| Paddle CUDA             | Yes            | Yes                   | Medium      | Same family likely         |
| Torch CUDA              | Yes            | Yes                   | Medium      | cu121                      |
| Torchvision CUDA        | Yes            | Yes                   | Low         | Same as Torch              |
| ONNX CUDA               | ❌             | Yes                   | HIGH        | Possible runtime conflicts |
| Multiple GPU Frameworks | Paddle + Torch | Paddle + Torch + ONNX | HIGHER in B | More native collisions     |
| CUDA Family Alignment   | cu121 likely   | cu121 likely          | Good        | Needs confirmation         |
| GPU Install Ownership   | requirements   | Docker/manual         | Better in B | Important nuance           |

---

# 3. Dockerfile-Level GPU Installation Comparison

## Service A — Dockerfile

| Component         | Installed?       | Version          | Install Type           |
| ----------------- | ---------------- | ---------------- | ---------------------- |
| paddlepaddle-gpu  | Yes              | `3.3.0`        | Direct GPU install     |
| paddleocr         | Via requirements | `3.4.0`        | pip                    |
| torch             | Yes              | `2.1.2+cu121`  | PyTorch CUDA index     |
| torchvision       | Yes              | `0.16.2+cu121` | PyTorch CUDA index     |
| ultralytics       | Via requirements | `8.3.235`      | pip                    |
| CUDA Runtime Base | Yes              | `12.2.2`       | NVIDIA container       |
| cuDNN             | Yes              | `8`            | Included in base image |

---

## Service B — Dockerfile

| Component         | Installed?       | Version          | Install Type     |
| ----------------- | ---------------- | ---------------- | ---------------- |
| paddlepaddle-gpu  | Yes/manual       | `3.3.0`        | Explicit install |
| paddleocr         | Via requirements | `3.4.0`        | pip              |
| torch             | Yes              | `2.1.2+cu121`  | Explicit install |
| torchvision       | Yes              | `0.16.2+cu121` | Explicit install |
| ultralytics       | Via requirements | `8.3.235`      | pip              |
| onnxruntime-gpu   | Via requirements | `1.17.0`       | pip              |
| CUDA Runtime Base | Yes              | `12.2.2`likely | NVIDIA container |
| cuDNN             | Yes              | `8`            | Included         |

---

# 4. Actual Architectural Difference

| Area              | Service A           | Service B                  |
| ----------------- | ------------------- | -------------------------- |
| Primary Role      | Batch GPU Processor | API + GPU Inference Engine |
| FastAPI           | No                  | Yes                        |
| Monitoring Stack  | Minimal             | Advanced                   |
| ONNX Runtime      | No                  | Yes                        |
| AWS Integration   | Yes                 | No                         |
| Logging Stack     | Basic               | Structured                 |
| GPU Complexity    | Medium              | Higher                     |
| Runtime Fragility | Medium              | Higher                     |

---

# 5. CUDA Compatibility Alignment Table

| Layer             | Service A       | Service B              | Compatible?   |
| ----------------- | --------------- | ---------------------- | ------------- |
| Host Driver       | CUDA 13 capable | CUDA 13 capable        | Yes           |
| Container Runtime | CUDA 12.2       | CUDA 12.2              | Yes           |
| Torch             | cu121           | cu121                  | Yes           |
| Paddle            | likely cu121    | likely cu121           | Yes           |
| ONNX Runtime      | ❌              | unknown provider build | Possible risk |

---

# 6. Native GPU Runtime Collision Risk

| Combination                       | Risk               |
| --------------------------------- | ------------------ |
| Paddle + Torch                    | Usually manageable |
| Paddle + Torch + ONNX Runtime GPU | Higher risk        |
| Paddle + TensorRT                 | Sensitive          |
| ONNX + TensorRT + Paddle          | Very sensitive     |

---

# 7. Most Important Nuances

| Nuance                                                 | Explanation                           |
| ------------------------------------------------------ | ------------------------------------- |
| Host driver version ≠ container CUDA version          | Driver only needs to be new enough    |
| cu121 means CUDA 12.1 wheel build                      | Not host toolkit version              |
| Docker does NOT fully isolate GPU runtime              | GPU libs still interact               |
| Paddle is more fragile than Torch                      | Especially mixed-runtime environments |
| ONNX Runtime GPU can introduce CUDA provider conflicts | Common issue                          |
| Same version does NOT guarantee runtime stability      | Native libs matter                    |
| Installation order matters                             | pip can mutate dependencies           |

---

# 8. Your Current Likely Runtime Stack

```text
HOST
 └── NVIDIA Driver (CUDA 13 capable)

DOCKER
 └── CUDA 12.2 Runtime

PYTHON ENV
 ├── Paddle 3.3.0
 ├── PaddleOCR 3.4.0
 ├── Torch cu121
 ├── Torchvision cu121
 ├── Ultralytics
 └── ONNX Runtime GPU (Service B only)
```

---

# 9. Most Probable Instability Sources

| Probability | Cause                          |
| ----------- | ------------------------------ |
| VERY HIGH   | ONNX Runtime GPU conflict      |
| HIGH        | Mixed GPU frameworks           |
| HIGH        | Paddle native CUDA sensitivity |
| MEDIUM      | pip dependency mutation        |
| LOW         | NVIDIA driver issue            |
| LOW         | GPU hardware issue             |

---

# 10. Best Immediate Stabilization Strategy

| Action                                    | Priority  |
| ----------------------------------------- | --------- |
| Remove ONNX Runtime GPU temporarily       | VERY HIGH |
| Keep all frameworks in same CUDA family   | VERY HIGH |
| Install GPU frameworks ONLY in Dockerfile | HIGH      |
| Add runtime validation checks             | HIGH      |
| Lock protobuf version                     | HIGH      |
| Separate OCR and YOLO services later      | MEDIUM    |

* Specific cross-chat memory path for that repo
