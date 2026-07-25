import os
import requests
from config import FACEPP_API_KEY, FACEPP_API_SECRET, FACEPP_CONFIDENCE_THRESHOLD

FACEPP_BASE_URL = "https://api-us.faceplusplus.com/facepp/v3"

class FaceEngine:
    def __init__(self):
        self.api_key = FACEPP_API_KEY
        self.api_secret = FACEPP_API_SECRET

    def _get_base_payload(self):
        return {
            'api_key': self.api_key,
            'api_secret': self.api_secret
        }

    def detect_faces(self, image_file_or_url):
        """
        Detect faces using Face++. 
        Accepts either a local file object (or path) or a Cloudinary URL.
        """
        if not self.api_key:
            return []
            
        url = f"{FACEPP_BASE_URL}/detect"
        payload = self._get_base_payload()
        payload['return_attributes'] = 'none'
        
        files = None
        if isinstance(image_file_or_url, str) and image_file_or_url.startswith('http'):
            payload['image_url'] = image_file_or_url
        else:
            if isinstance(image_file_or_url, str):
                f = open(image_file_or_url, 'rb')
                files = {'image_file': f}
            else:
                image_file_or_url.seek(0)
                filename = getattr(image_file_or_url, 'filename', 'image.jpg')
                files = {'image_file': (filename, image_file_or_url.read())}

        try:
            response = requests.post(url, data=payload, files=files)
            res_data = response.json()
            
            if 'faces' not in res_data:
                return []
                
            detected = []
            for face in res_data['faces']:
                rect = face['face_rectangle']
                # Store face_token instead of embedding
                detected.append({
                    'face_token': face['face_token'],
                    'bbox': [rect['left'], rect['top'], rect['width'], rect['height']],
                    'confidence': 1.0 # Face++ doesn't return confidence for detection by default unless requested, assume 1.0
                })
            return detected
        except Exception as e:
            print(f"Face++ Detect Error: {e}")
            return []
        finally:
            if files and isinstance(image_file_or_url, str):
                files['image_file'].close()

    def create_faceset(self, event_id):
        url = f"{FACEPP_BASE_URL}/faceset/create"
        payload = self._get_base_payload()
        payload['outer_id'] = event_id
        
        try:
            requests.post(url, data=payload)
            # We ignore errors if it already exists
        except Exception:
            pass

    def add_face_to_faceset(self, event_id, face_token):
        url = f"{FACEPP_BASE_URL}/faceset/addface"
        payload = self._get_base_payload()
        payload['outer_id'] = event_id
        payload['face_tokens'] = face_token
        
        try:
            requests.post(url, data=payload)
        except Exception as e:
            print(f"Face++ AddFace Error: {e}")

    def delete_faceset(self, event_id):
        url = f"{FACEPP_BASE_URL}/faceset/delete"
        payload = self._get_base_payload()
        payload['outer_id'] = event_id
        payload['check_empty'] = 0
        try:
            requests.post(url, data=payload)
        except Exception:
            pass

    def match_selfie_against_event(self, selfie_file, event_id, stored_faces=None):
        """
        Search for the selfie in the event's FaceSet.
        """
        if not self.api_key:
            return {'error': 'Face++ API Key not configured.'}
            
        url = f"{FACEPP_BASE_URL}/search"
        payload = self._get_base_payload()
        payload['outer_id'] = event_id
        payload['return_result_count'] = 5  # Return top 5 matches
        
        if isinstance(selfie_file, str) and selfie_file.startswith('http'):
            payload['image_url'] = selfie_file
            files = None
        else:
            if isinstance(selfie_file, str):
                f = open(selfie_file, 'rb')
                files = {'image_file': f}
            else:
                selfie_file.seek(0)
                filename = getattr(selfie_file, 'filename', 'image.jpg')
                files = {'image_file': (filename, selfie_file.read())}
                
        try:
            response = requests.post(url, data=payload, files=files)
            res_data = response.json()
            
            if 'error_message' in res_data:
                return {'error': res_data['error_message']}
                
            if 'results' not in res_data:
                return {'matches': [], 'selfie_faces_found': 0}
                
            matched_images = {}
            # Need to map Face++ face_token back to our database images
            # stored_faces is passed from database.get_faces_by_event(event_id)
            token_to_record = {f['face_token']: f for f in stored_faces if f.get('face_token')}
                
            for match in res_data['results']:
                confidence = match['confidence']
                if confidence >= FACEPP_CONFIDENCE_THRESHOLD:
                    token = match['face_token']
                    if token in token_to_record:
                        record = token_to_record[token]
                        image_id = record['image_id']
                        
                        if image_id not in matched_images or confidence > matched_images[image_id]['confidence_percentage']:
                            matched_images[image_id] = {
                                'image_id': image_id,
                                'image_path': record['image_path'],
                                'filename': record['filename'],
                                'similarity': confidence / 100.0,
                                'confidence_percentage': confidence,
                                'bounding_box': record['bounding_box']
                            }
                            
            sorted_results = sorted(matched_images.values(), key=lambda x: x['similarity'], reverse=True)
            return {'matches': sorted_results, 'selfie_faces_found': len(res_data.get('faces', []))}
            
        except Exception as e:
            return {'error': str(e)}
        finally:
            if files and isinstance(selfie_file, str):
                files['image_file'].close()

face_engine = FaceEngine()
