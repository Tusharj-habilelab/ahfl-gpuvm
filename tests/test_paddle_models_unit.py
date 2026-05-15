"""
Unit tests for PaddleOCR models used in AHFL-Masking 1.1

Run with: pytest tests/test_paddle_models_unit.py -v
"""

import pytest
import cv2
import numpy as np
from pathlib import Path
from paddleocr import PaddleOCR, DocImgOrientationClassification


@pytest.fixture(scope="module")
def sample_image():
    """Create a synthetic test image with text"""
    img = np.ones((400, 600, 3), dtype=np.uint8) * 255
    cv2.putText(img, "1234 5678 9012", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    cv2.putText(img, "Test Aadhaar Card", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(img, "Name: John Doe", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    return img


@pytest.fixture(scope="module")
def rotated_image(sample_image):
    """Create rotated versions of test image"""
    return {
        0: sample_image,
        90: cv2.rotate(sample_image, cv2.ROTATE_90_CLOCKWISE),
        180: cv2.rotate(sample_image, cv2.ROTATE_180),
        270: cv2.rotate(sample_image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    }


class TestDetectionModel:
    """Test PP-OCRv5_server_det - Text detection model"""
    
    @pytest.fixture(scope="class")
    def ocr_det(self):
        return PaddleOCR(lang='en', use_angle_cls=False, det=True, rec=False, use_gpu=False)
    
    def test_detection_initialization(self, ocr_det):
        """Test model loads successfully"""
        assert ocr_det is not None
    
    def test_detection_finds_text_regions(self, ocr_det, sample_image):
        """Test detection finds text bounding boxes"""
        result = ocr_det.ocr(sample_image, det=True, rec=False)
        assert result is not None
        assert len(result) > 0
        assert result[0] is not None
        assert len(result[0]) >= 3
    
    def test_detection_bbox_format(self, ocr_det, sample_image):
        """Test bounding box format is correct"""
        result = ocr_det.ocr(sample_image, det=True, rec=False)
        for box in result[0]:
            assert len(box[0]) == 4
            for point in box[0]:
                assert len(point) == 2
                assert isinstance(point[0], (int, float))
                assert isinstance(point[1], (int, float))


class TestRecognitionModel:
    """Test en_PP-OCRv5_mobile_rec - Text recognition model"""
    
    @pytest.fixture(scope="class")
    def ocr_rec(self):
        return PaddleOCR(lang='en', use_angle_cls=False, use_gpu=False)
    
    def test_recognition_initialization(self, ocr_rec):
        """Test model loads successfully"""
        assert ocr_rec is not None
    
    def test_recognition_reads_text(self, ocr_rec, sample_image):
        """Test recognition extracts text correctly"""
        result = ocr_rec.ocr(sample_image)
        assert result is not None
        assert len(result) > 0
        assert result[0] is not None
        
        texts = [line[1][0] for line in result[0]]
        all_text = ' '.join(texts)
        assert any(char.isdigit() for char in all_text)
    
    def test_recognition_confidence_scores(self, ocr_rec, sample_image):
        """Test confidence scores are valid"""
        result = ocr_rec.ocr(sample_image)
        for line in result[0]:
            text, conf = line[1]
            assert 0.0 <= conf <= 1.0
            assert isinstance(text, str)


class TestTextlineOrientationModel:
    """Test PP-LCNet_x1_0_textline_ori - Text line orientation classifier"""
    
    @pytest.fixture(scope="class")
    def ocr_textline(self):
        return PaddleOCR(lang='en', use_textline_orientation=True, use_gpu=False)
    
    def test_textline_orientation_initialization(self, ocr_textline):
        """Test model loads successfully"""
        assert ocr_textline is not None
    
    def test_textline_orientation_processing(self, ocr_textline, sample_image):
        """Test processes image with text line orientation"""
        result = ocr_textline.ocr(sample_image)
        assert result is not None
        assert len(result) > 0
        assert result[0] is not None


class TestDocOrientationModel:
    """Test PP-LCNet_x1_0_doc_ori - Document orientation classifier"""
    
    @pytest.fixture(scope="class")
    def doc_ori(self):
        return DocImgOrientationClassification(use_gpu=False)
    
    def test_doc_orientation_initialization(self, doc_ori):
        """Test model loads successfully"""
        assert doc_ori is not None
    
    def test_doc_orientation_detects_angle(self, doc_ori, sample_image):
        """Test detects orientation angle"""
        result = doc_ori(sample_image)
        assert 'angle' in result
        assert 'confidence' in result
        assert result['angle'] in [0, 90, 180, 270]
        assert 0.0 <= result['confidence'] <= 1.0
    
    def test_doc_orientation_all_rotations(self, doc_ori, rotated_image):
        """Test detects all rotation angles"""
        for angle in [0, 90, 180, 270]:
            result = doc_ori(rotated_image[angle])
            assert result['angle'] in [0, 90, 180, 270]


class TestUVDocModel:
    """Test UVDoc - Document unwarping model"""
    
    def test_uvdoc_availability(self):
        """Test UVDoc can be imported"""
        try:
            from paddleocr import PPStructure
            assert PPStructure is not None
        except ImportError:
            pytest.skip("PPStructure not available")


class TestFullPipeline:
    """Test complete OCR pipeline as used in application"""
    
    @pytest.fixture(scope="class")
    def ocr_full(self):
        return PaddleOCR(lang='en', use_textline_orientation=True, use_gpu=False)
    
    def test_full_pipeline_initialization(self, ocr_full):
        """Test full pipeline loads"""
        assert ocr_full is not None
    
    def test_full_pipeline_processes_image(self, ocr_full, sample_image):
        """Test full pipeline processes image end-to-end"""
        result = ocr_full.ocr(sample_image)
        assert result is not None
        assert len(result) > 0
        assert result[0] is not None
    
    def test_full_pipeline_output_format(self, ocr_full, sample_image):
        """Test output format matches expected structure"""
        result = ocr_full.ocr(sample_image)
        for line in result[0]:
            assert len(line) == 2
            bbox, text_info = line
            assert len(bbox) == 4
            assert len(text_info) == 2
            text, conf = text_info
            assert isinstance(text, str)
            assert 0.0 <= conf <= 1.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
