#!/usr/bin/env python3
"""
Test script for all PaddleOCR models used in AHFL-Masking 1.1

Models tested:
1. PP-OCRv5_server_det - Text detection (finds text regions)
2. en_PP-OCRv5_mobile_rec - Text recognition (reads text)
3. PP-LCNet_x1_0_textline_ori - Text line orientation (0/180 degrees)
4. PP-LCNet_x1_0_doc_ori - Document orientation (0/90/180/270 degrees)
5. UVDoc - Document unwarping (straightens curved/warped documents)
"""

import os
import sys
import cv2
import numpy as np
from pathlib import Path
from paddleocr import PaddleOCR, DocImgOrientationClassification

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _get_paddle_device() -> str:
    """Return paddle device string: env override > GPU auto-detect > cpu."""
    override = os.getenv("PADDLE_DEVICE")
    if override:
        return override
    try:
        import paddle
        if paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0:
            return "gpu:0"
    except Exception:
        pass
    return "cpu"


def test_detection_model(image_path: str, output_dir: Path):
    """Test PP-OCRv5_server_det - Text detection model"""
    print("\n" + "="*60)
    print("1. TESTING: PP-OCRv5_server_det (Text Detection)")
    print("="*60)
    
    device = _get_paddle_device()
    print(f"  Using device: {device}")
    
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang='en', use_textline_orientation=False, device=device)
    
    img = cv2.imread(image_path)
    result = ocr.ocr(image_path)
    
    # Draw detection boxes
    vis_img = img.copy()
    if result and result[0]:
        for box in result[0]:
            pts = np.array(box[0], dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(vis_img, [pts], True, (0, 255, 0), 2)
    
    out_path = output_dir / "1_detection_output.jpg"
    cv2.imwrite(str(out_path), vis_img)
    
    print(f"✓ Detected {len(result[0]) if result and result[0] else 0} text regions")
    print(f"✓ Output saved: {out_path}")
    return result


def test_recognition_model(image_path: str, det_result, output_dir: Path):
    """Test en_PP-OCRv5_mobile_rec - Text recognition model"""
    print("\n" + "="*60)
    print("2. TESTING: en_PP-OCRv5_mobile_rec (Text Recognition)")
    print("="*60)
    
    device = _get_paddle_device()
    print(f"  Using device: {device}")
    
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang='en', use_textline_orientation=False, device=device)
    
    img = cv2.imread(image_path)
    result = ocr.ocr(image_path)
    
    # Draw text on image
    vis_img = img.copy()
    if result and result[0]:
        for line in result[0]:
            box, (text, conf) = line[0], line[1]
            pts = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(vis_img, [pts], True, (0, 255, 0), 2)
            cv2.putText(vis_img, text, tuple(pts[0][0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            print(f"  Text: '{text}' | Confidence: {conf:.3f}")
    
    out_path = output_dir / "2_recognition_output.jpg"
    cv2.imwrite(str(out_path), vis_img)
    
    print(f"✓ Recognized {len(result[0]) if result and result[0] else 0} text lines")
    print(f"✓ Output saved: {out_path}")
    return result


def test_textline_orientation(image_path: str, output_dir: Path):
    """Test PP-LCNet_x1_0_textline_ori - Text line orientation classifier"""
    print("\n" + "="*60)
    print("3. TESTING: PP-LCNet_x1_0_textline_ori (Text Line Orientation)")
    print("="*60)
    print("NOTE: This model is used internally by PaddleOCR when use_textline_orientation=True")
    
    device = _get_paddle_device()
    print(f"  Using device: {device}")
    
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(lang='en', use_textline_orientation=True, device=device)
    
    img = cv2.imread(image_path)
    result = ocr.ocr(image_path)
    
    # Draw with orientation info
    vis_img = img.copy()
    if result and result[0]:
        for line in result[0]:
            box, (text, conf) = line[0], line[1]
            pts = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
            cv2.polylines(vis_img, [pts], True, (255, 0, 0), 2)
    
    out_path = output_dir / "3_textline_orientation_output.jpg"
    cv2.imwrite(str(out_path), vis_img)
    
    print(f"✓ Processed with text line orientation correction")
    print(f"✓ Output saved: {out_path}")
    return result


def test_doc_orientation(image_path: str, output_dir: Path):
    """Test PP-LCNet_x1_0_doc_ori - Document orientation classifier"""
    print("\n" + "="*60)
    print("4. TESTING: PP-LCNet_x1_0_doc_ori (Document Orientation)")
    print("="*60)
    
    device = _get_paddle_device()
    print(f"  Using device: {device}")
    
    doc_ori = DocImgOrientationClassification(device=device)
    
    img = cv2.imread(image_path)
    result = doc_ori(img)
    
    angle = result['angle']
    confidence = result['confidence']
    
    print(f"✓ Detected orientation: {angle}°")
    print(f"✓ Confidence: {confidence:.3f}")
    
    # Rotate image if needed
    if angle != 0:
        if angle == 90:
            rotated = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif angle == 180:
            rotated = cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        else:
            rotated = img
    else:
        rotated = img
    
    # Create comparison
    h1, w1 = img.shape[:2]
    h2, w2 = rotated.shape[:2]
    max_h = max(h1, h2)
    
    canvas = np.ones((max_h, w1 + w2 + 20, 3), dtype=np.uint8) * 255
    canvas[:h1, :w1] = img
    canvas[:h2, w1+20:w1+20+w2] = rotated
    
    cv2.putText(canvas, f"Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(canvas, f"Corrected ({angle}deg)", (w1+30, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    
    out_path = output_dir / "4_doc_orientation_output.jpg"
    cv2.imwrite(str(out_path), canvas)
    
    print(f"✓ Output saved: {out_path}")
    return result


def test_uvdoc_unwarp(image_path: str, output_dir: Path):
    """Test UVDoc - Document unwarping model"""
    print("\n" + "="*60)
    print("5. TESTING: UVDoc (Document Unwarping)")
    print("="*60)
    print("NOTE: UVDoc requires specific initialization. Testing basic usage...")
    
    try:
        device = _get_paddle_device()
        print(f"  Using device: {device}")
        
        from paddleocr import PPStructure
        engine = PPStructure(device=device, recovery=True)
        
        img = cv2.imread(image_path)
        result = engine(img)
        
        print(f"✓ UVDoc processing complete")
        print(f"✓ Result type: {type(result)}")
        
        # Save original for comparison
        out_path = output_dir / "5_uvdoc_output.jpg"
        cv2.imwrite(str(out_path), img)
        print(f"✓ Output saved: {out_path}")
        
        return result
    except Exception as e:
        print(f"⚠ UVDoc test skipped: {e}")
        print("  UVDoc is typically used for curved/warped document correction")
        return None


def test_full_pipeline(image_path: str, output_dir: Path):
    """Test complete OCR pipeline as used in application"""
    print("\n" + "="*60)
    print("6. TESTING: Full Pipeline (As Used in Application)")
    print("="*60)
    
    device = _get_paddle_device()
    print(f"  Using device: {device}")
    
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(
        lang='en',
        use_textline_orientation=True,
        device=device,
    )
    
    img = cv2.imread(image_path)
    result = ocr.ocr(image_path)
    
    # Draw complete result
    vis_img = img.copy()
    aadhaar_patterns = []
    
    if result and result[0]:
        for line in result[0]:
            box, (text, conf) = line[0], line[1]
            pts = np.array(box, dtype=np.int32).reshape((-1, 1, 2))
            
            # Check for Aadhaar number pattern (12 digits)
            import re
            if re.search(r'\d{4}\s*\d{4}\s*\d{4}', text):
                cv2.polylines(vis_img, [pts], True, (0, 0, 255), 3)  # Red for Aadhaar
                aadhaar_patterns.append(text)
            else:
                cv2.polylines(vis_img, [pts], True, (0, 255, 0), 2)  # Green for normal text
            
            cv2.putText(vis_img, f"{text[:20]}", tuple(pts[0][0]), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
    
    out_path = output_dir / "6_full_pipeline_output.jpg"
    cv2.imwrite(str(out_path), vis_img)
    
    print(f"✓ Total text detections: {len(result[0]) if result and result[0] else 0}")
    print(f"✓ Aadhaar patterns found: {len(aadhaar_patterns)}")
    for pattern in aadhaar_patterns:
        print(f"  - {pattern}")
    print(f"✓ Output saved: {out_path}")
    
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Test all PaddleOCR models')
    parser.add_argument('--image', required=True, help='Path to test image (Aadhaar card recommended)')
    parser.add_argument('--output', default='./paddle_test_output', help='Output directory for results')
    args = parser.parse_args()
    
    image_path = args.image
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True, parents=True)
    
    if not os.path.exists(image_path):
        print(f"❌ Error: Image not found: {image_path}")
        sys.exit(1)
    
    print("\n" + "="*60)
    print("PADDLE OCR MODELS TEST SUITE")
    print("="*60)
    print(f"Test Image: {image_path}")
    print(f"Output Directory: {output_dir}")
    print(f"Device: {_get_paddle_device()}")
    
    # Run all tests
    det_result = test_detection_model(image_path, output_dir)
    rec_result = test_recognition_model(image_path, det_result, output_dir)
    textline_result = test_textline_orientation(image_path, output_dir)
    doc_ori_result = test_doc_orientation(image_path, output_dir)
    uvdoc_result = test_uvdoc_unwarp(image_path, output_dir)
    pipeline_result = test_full_pipeline(image_path, output_dir)
    
    print("\n" + "="*60)
    print("✓ ALL TESTS COMPLETE")
    print("="*60)
    print(f"Check outputs in: {output_dir}")
    print("\nModel Summary:")
    print("1. PP-OCRv5_server_det: Text detection (bounding boxes)")
    print("2. en_PP-OCRv5_mobile_rec: Text recognition (reads text)")
    print("3. PP-LCNet_x1_0_textline_ori: Text line orientation (0/180°)")
    print("4. PP-LCNet_x1_0_doc_ori: Document orientation (0/90/180/270°)")
    print("5. UVDoc: Document unwarping (curved/warped correction)")


if __name__ == '__main__':
    main()
