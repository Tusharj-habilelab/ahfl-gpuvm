# AHFL Flow In Simple Words (Hinglish, No Code)

Ye document code explain nahi karta, simple language me batata hai ki image aane ke baad system uske saath step-by-step kya karta hai.

---

## 1) Image sabse pehle kahan aati hai?

User jab file upload karta hai, file pehle **API Gateway** me aati hai.

- File type check hota hai (`pdf/jpg/jpeg/png`).
- File size check hota hai.
- API key validate hoti hai.
- Uske baad gateway file ko **masking-engine** service ko forward kar deta hai.

Is point tak masking start nahi hui hoti. Yeh sirf security + validation + forwarding stage hai.

---

## 2) Masking-engine me aake kya hota hai?

Masking-engine file ko disk pe save karta hai aur phir:

- Agar file image hai: direct image pipeline chalta hai.
- Agar file PDF hai: PDF ko pages me todta hai, har page image banata hai, phir har page pe same image pipeline chalata hai.

Final me page-wise report ban jaati hai.

---

## 3) Real masking pipeline ka main brain kya hai?

Real logic `core/pipeline.py` me hai.

Sabse pehla kaam:

1. Image channels normalize (gray/RGBA ko proper BGR banata hai).
2. Shared OCR model instance load karta hai (reuse ke liye).
3. **Router** decide karta hai ki document:
   - `form` lane me jayega
   - `card` lane me jayega
   - ya `uncertain` lane (safe fallback)

---

## 4) Router ka decision simple words me

Router light OCR chalata hai (full OCR nahi, quick OCR):

- Image ko chhota karke text tokens nikalta hai.
- Keywords, Aadhaar number pattern, form-patterns dekhkar confidence banata hai.
- Agar confidence low hai, woh `uncertain` me bhej deta hai.

Important:

- `uncertain` lane safe side hai, aur usually card-like heavy pipeline chalata hai.
- Isliye form dikhta hua document bhi kabhi uncertain lane me ja sakta hai.

---

## 5) Agar lane = form ho to exact kya hota hai?

Form lane me system heavy YOLO orientation sweep nahi chalata. Iska flow:

1. Document orientation model dekhkar form ko 0/90/180/270 me seedha karta hai.
2. Full image OCR chalata hai.
3. Skip keyword aur PAN check karta hai.
   - Agar skip hit hua: yahin stop, masking skip.
4. OCR tokens me Aadhaar patterns dhoondta hai.
5. Jo sensitive regions milte hain unpe black mask draw karta hai.
6. Final masked image aur report return.

Simple: **Form lane = OCR-first masking**.

---

## 6) Agar lane = card ya uncertain ho to exact kya hota hai?

Yahan full heavy pipeline chalti hai:

1. **Orientation sweep**:
   - Image multiple angles me test hoti hai (0,45,90,135,180,225,270,315).
   - Har angle pe Aadhaar gate score nikalta hai.
   - Best score wala angle winner banta hai.

2. **Aadhaar Gate** (winner angle pe):
   - `main.pt` detections
   - front/back classifier filter (`front_back_detect.pt`)
   - Aadhaar crop ke andar `best.pt` detections
   - merge karke final detections set banata hai.

3. OCR card-crops pe chalti hai (ya fallback full image pe).
4. Aadhaar verification text basis pe hoti hai.
5. Skip/PAN checks hoti hain.
6. Optional PVC photo masking hota hai (`yolov8n.pt` person model).
7. YOLO detections se number/QR masking hoti hai.
8. OCR pattern masking second layer ke roop me chalti hai.
9. Agar required ho to image original orientation ke paas rotate-back hoti hai.
10. Final masked output save/report.

Simple: **Card/uncertain lane = orientation + multi-model + dual masking**.

---

## 7) Kaunsa model kab use hota hai? (Normal words)

### `main.pt`
- Broad card-related detections ke liye.
- Aadhaar card locate karne ka base signal deta hai.

### `front_back_detect.pt`
- Aadhaar detection ko verify/filter karta hai (front/back/pvc side intelligence).

### `best.pt`
- Number/QR/masked variants jaisi finer detections deta hai.
- Aadhaar crop ke andar chalaya jata hai for better precision.

### `yolov8n.pt`
- PVC Aadhaar me person photo detect karne ke liye (photo masking stage).

### PaddleOCR
- Text extraction ke liye:
  - Router lite text
  - Main OCR
  - Number verification
  - Form pattern masking

### Doc orientation model
- Document ko 0/90/180/270 correct orientation dene ke liye.

---

## 8) Lane-wise cards ka behavior

- **Form lane**: Document ko text-heavy form maan kar OCR masking karta hai.
- **Card lane**: Card-focused logic chalti hai (angle + gate + card crop + number/QR focus).
- **Uncertain lane**: Risk avoid karne ke liye card lane jaisa strong pipeline chalata hai.

---

## 9) Batch processor me extra kya hota hai?

Batch service same core pipeline per file/page chalata hai, lekin extra kaam karta hai:

- Folder/S3 style batch iteration.
- PDF page loops.
- DynamoDB status workflow (`PENDING -> PROCESSING -> COMPLETED/ERROR`).
- Aggregated report fields write karta hai.

Yaani masking logic same hai, orchestration + logging enterprise-style hai.

---

## 10) `.py` files ka clear runtime map (jo actually kaam me aate hain)

Neeche list **aapke project structure** ke hisab se break ki gayi hai:

## A) Primary live runtime files (core flow me directly)

- `services/api-gateway/main.py`
- `services/masking-engine/engine.py`
- `services/batch-processor/batch.py`
- `core/pipeline.py`
- `core/router.py`
- `core/aadhaar_gate.py`
- `core/classifiers.py`
- `core/spatial.py`
- `core/config.py`
- `core/models/yolo_runner.py`
- `core/ocr/paddle.py`
- `core/ocr/ocr_adapter.py`
- `core/ocr/masking.py`
- `core/utils/angle_detector.py`
- `core/db/database.py` (batch DB writes)
- `core/__init__.py`, `core/models/__init__.py`, `core/db/__init__.py`, `core/ocr/__init__.py`, `core/utils/__init__.py` (export/import glue)

## B) Runtime-support / utility (main masking path ka direct critical part nahi)

- `core/db/log_writer.py` (shared DB helper, reporting/support use)
- `services/batch-processor/utils/file_paths.py` (DB query utility, not core masking step)
- `core/utils/file_utils.py` (file helper utilities)

## C) Present but main masking pipeline me normally use nahi hote

- `core/utils/count_processed_files.py`
- `core/utils/counts.py`

## D) Debug/forensic specific (production masking API path ka part nahi)

- `pipeline-visualizer-per-step.py`

---

## 11) Ek line me full safar

Image upload hoti hai -> gateway validate karta hai -> masking-engine pipeline call hoti hai -> router lane choose karta hai -> lane ke hisab se OCR-only ya orientation+YOLO+OCR masking chalti hai -> final masked image + report return hota hai -> batch mode me yahi result DynamoDB workflow ke saath store hota hai.

