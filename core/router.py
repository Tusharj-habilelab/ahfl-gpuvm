"""
router.py — Document lane classification for AHFL-Masking 1.1

Routes incoming documents to appropriate processing lanes to avoid wasting
compute on obvious forms while preserving card detection accuracy.

Lanes:
  - form: OCR-first path, skips heavy YOLO orientation/gate
  - card: Full YOLO gate + orientation + verification
  - uncertain: Safe fallback with full gate

Router uses lightweight OCR-based keyword matching + text density analysis.
"""

import logging
import re
from typing import Dict, Tuple

import numpy as np
from core.config import (
    ROUTER_BIAS_RATIO,
    ROUTER_CARD_CONF_DIVISOR,
    ROUTER_CARD_TOKEN_MAX,
    ROUTER_CONFIDENCE_THRESHOLD,
    ROUTER_FORM_CONF_DIVISOR,
    ROUTER_FORM_TOKEN_MIN,
    ROUTER_MIXED_CONFIDENCE,
    ROUTER_TABLE_SIGNAL_MIN,
    SKIP_KEYWORDS,
)

log = logging.getLogger(__name__)


def _normalize_text(text: str) -> str:
    """
    Normalize text for keyword matching.
    
    Removes punctuation, collapses whitespace, converts to lowercase.
    Handles OCR noise and formatting variants.
    """
    # Remove common punctuation
    text = re.sub(r'[.:;,\-_(){}[\]]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Lowercase and strip
    return text.lower().strip()


def _contains_card_signals(tokens: list, normalized_text: str) -> Tuple[int, list]:
    """
    Check for strong Aadhaar card signals in OCR tokens.
    
    Returns:
        (signal_count, matched_keywords)
    """
    card_keywords = [
        'your aadhaar no',
        'uidai',
        'unique identification',
        'government of india',
        'enrolment no',
    ]
    
    signal_count = 0
    matched = []
    
    # Check card-specific phrases
    for keyword in card_keywords:
        if keyword in normalized_text:
            signal_count += 2  # Strong signal
            matched.append(keyword)
    
    # Check for Aadhaar-like 12-digit numbers
    # Pattern: XXXX XXXX XXXX or XXXX-XXXX-XXXX or continuous 12 digits
    aadhaar_pattern = r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
    if re.search(aadhaar_pattern, normalized_text):
        signal_count += 1
        matched.append('12_digit_pattern')
    
    # Check for compact card-like layout cues
    # If text is concentrated (low token count but mentions aadhaar/aadhar)
    if ('aadhaar' in normalized_text or 'aadhar' in normalized_text):
        if len(tokens) < ROUTER_CARD_TOKEN_MAX:  # Compact text suggests card, not form
            signal_count += 1
            matched.append('compact_aadhaar_mention')
    
    return signal_count, matched


def _contains_form_signals(tokens: list, normalized_text: str) -> Tuple[int, list]:
    """
    Check for strong application form signals in OCR tokens.
    
    Returns:
        (signal_count, matched_keywords)
    """
    form_keywords = [
        'applicant',
        'spouse',
        'loan code',
        'loan account',
        'disb dt',
        'disbursement',
        'aadhaar card no',
        'aadhaar uid',
        'pmay',
        'pmay beneficiary',
        'sanctioned amount',
        'application form',
        'co applicant',
    ]
    
    signal_count = 0
    matched = []
    
    for keyword in form_keywords:
        if keyword in normalized_text:
            signal_count += 1
            matched.append(keyword)
    
    # Check for table-like structure indicators
    table_indicators = ['s no', 'sr no', 'serial no', 'name of', 'date of birth', 'gender']
    table_count = sum(1 for ind in table_indicators if ind in normalized_text)
    if table_count >= ROUTER_TABLE_SIGNAL_MIN:
        signal_count += 2
        matched.append('table_structure')
    
    # High token count suggests form with lots of fields
    if len(tokens) > ROUTER_FORM_TOKEN_MIN:
        signal_count += 1
        matched.append('high_token_count')
    
    return signal_count, matched


def _contains_skip_signals(normalized_text: str) -> Tuple[bool, str]:
    """
    Check for skip keywords that should bypass masking entirely.
    
    Returns:
        (should_skip, matched_keyword)
    """
    for keyword in SKIP_KEYWORDS:
        if keyword in normalized_text:
            return True, keyword
    
    return False, None


def classify_document_lane(
    ocr_tokens: list,
    confidence_threshold: float = ROUTER_CONFIDENCE_THRESHOLD,
    debug: bool = False
) -> Dict[str, any]:
    """
    Classify document into processing lane based on OCR-lite signals.
    
    Args:
        ocr_tokens: List of text tokens from OCR-lite pass
        confidence_threshold: Minimum confidence to avoid uncertain lane (default 0.55)
        debug: If True, log detailed classification reasoning
    
    Returns:
        Dict with keys:
          - lane: 'form' | 'card' | 'uncertain'
          - confidence: float 0.0-1.0
          - card_signals: list of matched card keywords
          - form_signals: list of matched form keywords
          - skip_detected: bool
          - skip_keyword: str or None
          - reasoning: str (debug explanation)
    """
    if not ocr_tokens:
        return {
            'lane': 'uncertain',
            'confidence': 0.0,
            'card_signals': [],
            'form_signals': [],
            'skip_detected': False,
            'skip_keyword': None,
            'reasoning': 'No OCR tokens available'
        }
    
    # Build combined normalized text for phrase matching
    combined_text = ' '.join(ocr_tokens)
    normalized = _normalize_text(combined_text)
    
    # Check skip signals first
    should_skip, skip_keyword = _contains_skip_signals(normalized)
    if should_skip:
        log.info(f"Router: skip keyword detected: '{skip_keyword}'")
        return {
            'lane': 'form',  # Route to form lane for skip processing
            'confidence': 1.0,
            'card_signals': [],
            'form_signals': [],
            'skip_detected': True,
            'skip_keyword': skip_keyword,
            'reasoning': f'Skip keyword: {skip_keyword}'
        }
    
    # Analyze card and form signals
    card_count, card_matches = _contains_card_signals(ocr_tokens, normalized)
    form_count, form_matches = _contains_form_signals(ocr_tokens, normalized)
    
    # Compute confidence scores
    # Scale: 0-1, higher = more confident in classification
    total_signals = card_count + form_count
    if total_signals == 0:
        # No clear signals - route to uncertain
        lane = 'uncertain'
        confidence = 0.0
        reasoning = 'No strong card or form signals detected'
    elif card_count > form_count * ROUTER_BIAS_RATIO:
        # Strong card bias
        lane = 'card'
        confidence = min(1.0, card_count / ROUTER_CARD_CONF_DIVISOR)  # Cap at 1.0
        reasoning = f'Card signals dominant: {card_matches}'
    elif form_count > card_count * ROUTER_BIAS_RATIO:
        # Strong form bias
        lane = 'form'
        confidence = min(1.0, form_count / ROUTER_FORM_CONF_DIVISOR)  # Forms need slightly more evidence
        reasoning = f'Form signals dominant: {form_matches}'
    else:
        # Mixed signals or close call
        lane = 'uncertain'
        confidence = ROUTER_MIXED_CONFIDENCE
        reasoning = f'Mixed signals - card: {card_matches}, form: {form_matches}'
    
    # Apply confidence threshold
    # NOTE: Boundary logging helps diagnose close-call routing behavior.
    if lane != 'uncertain' and abs(confidence - confidence_threshold) <= 0.05:
        log.info(
            "Router threshold edge: "
            f"lane={lane} confidence={confidence:.2f} threshold={confidence_threshold:.2f}"
        )

    if confidence < confidence_threshold and lane != 'uncertain':
        original_lane = lane
        lane = 'uncertain'
        reasoning = f'{original_lane} confidence {confidence:.2f} below threshold {confidence_threshold}'
    
    result = {
        'lane': lane,
        'confidence': confidence,
        'card_signals': card_matches,
        'form_signals': form_matches,
        'skip_detected': False,
        'skip_keyword': None,
        'reasoning': reasoning
    }

    log.info(f"Router: lane={lane} confidence={confidence:.2f} reasoning={reasoning[:80]}")
    if debug:
        log.debug(f"Router decision detail: {result}")

    return result
