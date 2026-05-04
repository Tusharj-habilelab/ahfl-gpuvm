# Models directory — DO NOT commit model files to git

Place the following model files here before running the masking-engine:
- main.pt           (primary masking model)
- best.pt           (secondary/best masking model)
- front_back_detect.pt  (Aadhaar front/back classifier)
- yolov8n.pt        (YOLOv8n base model)

These files are referenced via env vars MODEL_MAIN, MODEL_BEST,
MODEL_FRONT_BACK, MODEL_YOLO_N in .env / docker-compose.yml.
