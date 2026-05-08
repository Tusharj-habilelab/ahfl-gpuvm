# core/classifiers.py (inside _get_classifier)

model_path = os.environ.get("MODEL_FRONT_BACK", "models/front_back_detect.pt")
log.info(f"Loading front/back classifier from {model_path} on {_DEVICE}")
_model = YOLO(model_path).to(_DEVICE)
log.info("✓ front/back classifier loaded")





# services/masking-engine/engine.py (startup_event)

import core.classifiers as classifiers
logger.info("Preloading front/back and person models...")
classifiers._get_classifier()
classifiers._get_person_model()
logger.info("Preload complete")
