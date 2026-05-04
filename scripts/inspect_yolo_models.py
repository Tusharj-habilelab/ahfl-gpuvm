from ultralytics import YOLO
import numpy as np
import os
from datetime import datetime

MODELS_DIR = os.path.join(os.path.dirname(__file__), "../services/masking-engine/models")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "reporting/model_metadata_report.txt")

MODEL_FILES = ["main.pt", "best.pt", "front_back_detect.pt", "yolov8n.pt"]

MODEL_ROLES = {
    "main.pt":             "Primary detector — locates raw Aadhaar number regions and QR codes",
    "best.pt":             "Masking state classifier — distinguishes masked vs unmasked regions",
    "front_back_detect.pt":"Side classifier — identifies Aadhaar front / back face",
    "yolov8n.pt":          "Base pretrained YOLOv8n (COCO) — backbone / fallback",
}

ENV_VARS = {
    "main.pt":             "MODEL_MAIN",
    "best.pt":             "MODEL_BEST",
    "front_back_detect.pt":"MODEL_FRONT_BACK",
    "yolov8n.pt":          "MODEL_YOLO_N",
}


def collect_metadata(model_path):
    model = YOLO(model_path)
    name = os.path.basename(model_path)
    size_mb = os.path.getsize(model_path) / (1024 * 1024)

    first_layer = model.model.model[0]
    try:
        in_ch = first_layer.conv.in_channels
        out_ch = first_layer.conv.out_channels
        kernel = list(first_layer.conv.kernel_size)
        stride_conv = list(first_layer.conv.stride)
    except AttributeError:
        in_ch = out_ch = kernel = stride_conv = "N/A"

    # count layers by type
    layer_types = {}
    for layer in model.model.model:
        t = type(layer).__name__
        layer_types[t] = layer_types.get(t, 0) + 1

    # dummy inference
    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
    try:
        results = model(dummy, verbose=False)
        inference_ok = True
        num_boxes = len(results[0].boxes)
    except Exception as e:
        inference_ok = False
        num_boxes = str(e)

    return {
        "name": name,
        "path": model_path,
        "size_mb": size_mb,
        "role": MODEL_ROLES.get(name, "Unknown"),
        "env_var": ENV_VARS.get(name, "Unknown"),
        "task": model.task,
        "num_classes": len(model.names),
        "classes": model.names,
        "architecture": model.model.__class__.__name__,
        "total_layers": len(model.model.model),
        "layer_type_counts": layer_types,
        "total_params": sum(p.numel() for p in model.model.parameters()),
        "trainable_params": sum(p.numel() for p in model.model.parameters() if p.requires_grad),
        "stride": model.model.stride.tolist(),
        "input_channels": in_ch,
        "first_layer_out_channels": out_ch,
        "first_layer_kernel": kernel,
        "first_layer_stride": stride_conv,
        "inference_ok": inference_ok,
        "dummy_boxes_detected": num_boxes,
    }


def format_report(all_meta):
    lines = []
    W = 72

    def rule(char="="):
        lines.append(char * W)

    def section(title):
        lines.append("")
        rule()
        lines.append(f"  {title}")
        rule()

    rule()
    lines.append("  AHFL MASKING ENGINE — MODEL METADATA REPORT")
    lines.append(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Models Dir: {MODELS_DIR}")
    rule()

    # ── Overview table ──────────────────────────────────────────────
    section("OVERVIEW")
    lines.append(f"  {'Model':<26} {'Task':<10} {'Classes':<9} {'Params':>10}  {'Size':>8}  Inference")
    lines.append("  " + "-" * 68)
    for m in all_meta:
        lines.append(
            f"  {m['name']:<26} {m['task']:<10} {m['num_classes']:<9} "
            f"{m['total_params']:>10,}  {m['size_mb']:>6.1f} MB  "
            f"{'✓ OK' if m['inference_ok'] else '✗ FAIL'}"
        )

    # ── Per-model detail ────────────────────────────────────────────
    for m in all_meta:
        section(f"MODEL: {m['name']}")

        lines.append(f"  Role        : {m['role']}")
        lines.append(f"  Env Var     : {m['env_var']}")
        lines.append(f"  File Path   : {m['path']}")
        lines.append(f"  File Size   : {m['size_mb']:.2f} MB")
        lines.append("")

        lines.append("  [ Architecture ]")
        lines.append(f"    Model Class      : {m['architecture']}")
        lines.append(f"    Task             : {m['task']}")
        lines.append(f"    Total Layers     : {m['total_layers']}")
        lines.append(f"    Total Parameters : {m['total_params']:,}")
        lines.append(f"    Trainable Params : {m['trainable_params']:,}")
        lines.append(f"    Detection Stride : {m['stride']}")
        lines.append("")

        lines.append("  [ First Layer (Stem Conv) ]")
        lines.append(f"    Input Channels   : {m['input_channels']}")
        lines.append(f"    Output Channels  : {m['first_layer_out_channels']}")
        lines.append(f"    Kernel Size      : {m['first_layer_kernel']}")
        lines.append(f"    Stride           : {m['first_layer_stride']}")
        lines.append("")

        lines.append("  [ Layer Type Breakdown ]")
        for ltype, count in sorted(m['layer_type_counts'].items(), key=lambda x: -x[1]):
            lines.append(f"    {ltype:<30} x{count}")
        lines.append("")

        lines.append(f"  [ Classes — {m['num_classes']} total ]")
        for idx, cls_name in m['classes'].items():
            lines.append(f"    [{idx:>2}]  {cls_name}")
        lines.append("")

        lines.append("  [ Dummy Inference (640×640 black image) ]")
        lines.append(f"    Status           : {'PASSED' if m['inference_ok'] else 'FAILED'}")
        lines.append(f"    Boxes Detected   : {m['dummy_boxes_detected']}")

    # ── Cross-model comparison ──────────────────────────────────────
    section("CROSS-MODEL COMPARISON")

    lines.append("  Input Resolution  : 640×640 (all models)")
    lines.append("  Input Channels    : 3 — RGB (all models)")
    lines.append("  Backbone          : YOLOv8n (all models)")
    lines.append("  Strides           : [8, 16, 32] (all models)")
    lines.append("")

    lines.append(f"  {'Model':<26} {'Layers':>7}  {'Params':>10}  {'Classes':>8}  {'Size':>8}")
    lines.append("  " + "-" * 65)
    for m in all_meta:
        lines.append(
            f"  {m['name']:<26} {m['total_layers']:>7}  "
            f"{m['total_params']:>10,}  {m['num_classes']:>8}  {m['size_mb']:>6.1f} MB"
        )

    lines.append("")
    lines.append("  Pipeline Order:")
    lines.append("    1. front_back_detect.pt  →  classify Aadhaar side (Front/Back)")
    lines.append("    2. main.pt               →  detect number + QR regions")
    lines.append("    3. best.pt               →  verify masking state per region")
    lines.append("    4. yolov8n.pt            →  base COCO backbone (not fine-tuned)")

    lines.append("")
    rule()
    lines.append("  END OF REPORT")
    rule()

    return "\n".join(lines)


if __name__ == "__main__":
    all_meta = []
    for name in MODEL_FILES:
        path = os.path.join(MODELS_DIR, name)
        if not os.path.exists(path):
            print(f"[SKIP] {name} not found")
            continue
        print(f"Inspecting {name}...")
        all_meta.append(collect_metadata(path))

    report = format_report(all_meta)
    print(report)

    with open(REPORT_PATH, "w") as f:
        f.write(report)
    print(f"\nReport saved → {REPORT_PATH}")
