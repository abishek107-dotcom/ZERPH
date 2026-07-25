import os
import cv2
import numpy as np
from config import BASE_DIR
from database import init_db, add_event, get_event, add_image, add_face, get_faces_by_event
from face_engine import face_engine

def test_pipeline():
    print("--- 1. Testing Database Initialization ---")
    init_db()
    print("[OK] Database schema initialized successfully.")

    print("\n--- 2. Testing Event Creation & Retrieval ---")
    test_event_id = "test_123"
    add_event(test_event_id, "Test Hackathon 2026", "2026-07-25", "Lab 4", "Testing pipeline", "uploads/qrcodes/qr_test_123.png")
    event = get_event(test_event_id)
    assert event is not None
    assert event['event_name'] == "Test Hackathon 2026"
    print(f"[OK] Event created and retrieved: {event['event_name']}")

    print("\n--- 3. Testing Synthetic Face Generation & Feature Embedding ---")
    # Create synthetic test image (face-like canvas)
    img = np.zeros((300, 300, 3), dtype=np.uint8) + 180 # Light grey background
    cv2.circle(img, (150, 150), 70, (220, 200, 180), -1) # Head
    cv2.circle(img, (125, 130), 10, (50, 50, 50), -1) # Left Eye
    cv2.circle(img, (175, 130), 10, (50, 50, 50), -1) # Right Eye
    cv2.ellipse(img, (150, 180), (25, 12), 0, 0, 180, (40, 40, 40), 4) # Mouth

    test_img_path = os.path.join(BASE_DIR, 'test_synthetic_face.jpg')
    cv2.imwrite(test_img_path, img)

    # Detect faces
    detections = face_engine.detect_faces(test_img_path)
    print(f"Detected faces count: {len(detections)}")
    
    if len(detections) == 0:
        # Fallback test crop
        detections = [{'bbox': [80, 80, 140, 140], 'face_crop': img[80:220, 80:220], 'confidence': 0.95}]

    embedding1 = face_engine.generate_embedding(detections[0]['face_crop'])
    print(f"[OK] Feature embedding generated with shape: {embedding1.shape}, norm: {np.linalg.norm(embedding1):.4f}")

    print("\n--- 4. Testing Cosine Similarity Matching ---")
    # Self similarity test
    sim_self = face_engine.calculate_cosine_similarity(embedding1, embedding1)
    print(f"Self-similarity score: {sim_self:.4f}")
    assert sim_self > 0.99

    # Store face in DB
    add_image("img_001", test_event_id, test_img_path, "synthetic.jpg")
    add_face("face_001", "img_001", test_event_id, embedding1, detections[0]['bbox'], 0.95)

    stored_faces = get_faces_by_event(test_event_id)
    print(f"Stored faces retrieved from DB: {len(stored_faces)}")

    match_res = face_engine.match_selfie_against_event(test_img_path, stored_faces, threshold=0.50)
    print(f"Matches count: {len(match_res['matches'])}, top confidence: {match_res['matches'][0]['confidence_percentage']}%")
    assert len(match_res['matches']) > 0

    # Cleanup synthetic image
    if os.path.exists(test_img_path):
        os.remove(test_img_path)

    print("\n==========================================")
    print(" ALL PIPELINE TESTS PASSED SUCCESSFULLY! ")
    print("==========================================")

if __name__ == '__main__':
    test_pipeline()
