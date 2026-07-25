import os
import json
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

# Initialize Supabase client globally
supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Supabase Client Error: {e}")

def init_db():
    # Database is initialized via Supabase SQL Editor manually.
    pass

def add_event(event_id, event_name, date, venue, description, qr_code_path):
    if not supabase: return
    data = {
        'event_id': event_id,
        'event_name': event_name,
        'date': date,
        'venue': venue,
        'description': description,
        'qr_code_path': qr_code_path
    }
    supabase.table('events').insert(data).execute()

def get_event(event_id):
    if not supabase: return None
    response = supabase.table('events').select('*').eq('event_id', event_id).execute()
    return response.data[0] if response.data else None

def get_all_events():
    if not supabase: return []
    events_res = supabase.table('events').select('*').order('created_at', desc=True).execute()
    events = events_res.data
    
    # Calculate counts per event
    for e in events:
        e_id = e['event_id']
        imgs = supabase.table('images').select('image_id', count='exact').eq('event_id', e_id).execute()
        faces = supabase.table('faces').select('face_id', count='exact').eq('event_id', e_id).execute()
        e['photo_count'] = imgs.count if imgs.count is not None else 0
        e['face_count'] = faces.count if faces.count is not None else 0
        
    return events

def delete_event(event_id):
    if not supabase: return False
    # Supabase foreign keys with ON DELETE CASCADE will handle images, faces, and search_logs.
    supabase.table('events').delete().eq('event_id', event_id).execute()
    return True

def add_image(image_id, event_id, image_path, filename):
    if not supabase: return
    data = {
        'image_id': image_id,
        'event_id': event_id,
        'image_path': image_path,
        'filename': filename
    }
    supabase.table('images').insert(data).execute()

def add_face(face_id, image_id, event_id, embedding_vector, bounding_box, confidence, face_token=None):
    if not supabase: return
    data = {
        'face_id': face_id,
        'image_id': image_id,
        'event_id': event_id,
        'embedding': embedding_vector if isinstance(embedding_vector, list) else (embedding_vector.tolist() if hasattr(embedding_vector, 'tolist') else embedding_vector),
        'face_token': face_token,
        'bounding_box': bounding_box,
        'confidence': float(confidence)
    }
    supabase.table('faces').insert(data).execute()

def get_faces_by_event(event_id):
    if not supabase: return []
    response = supabase.table('faces').select('*, images!inner(image_path, filename)').eq('event_id', event_id).execute()
    
    result = []
    for row in response.data:
        # Flatten the join
        image_data = row.pop('images')
        if isinstance(image_data, list):
            image_data = image_data[0] # Handle cases where postgrest returns a list
        row['image_path'] = image_data['image_path']
        row['filename'] = image_data['filename']
        result.append(row)
        
    return result

def log_search(search_id, event_id, matched_count, processing_time_ms):
    if not supabase: return
    data = {
        'search_id': search_id,
        'event_id': event_id,
        'matched_images_count': matched_count,
        'processing_time_ms': processing_time_ms
    }
    supabase.table('search_logs').insert(data).execute()

def get_dashboard_stats():
    if not supabase: return {'total_events': 0, 'total_photos': 0, 'total_faces': 0, 'total_searches': 0, 'storage_mb': 0, 'recent_searches': []}
    
    events_c = supabase.table('events').select('event_id', count='exact').execute().count
    photos_c = supabase.table('images').select('image_id', count='exact').execute().count
    faces_c = supabase.table('faces').select('face_id', count='exact').execute().count
    searches_c = supabase.table('search_logs').select('search_id', count='exact').execute().count
    
    recent_res = supabase.table('search_logs').select('*, events!inner(event_name)').order('timestamp', desc=True).limit(5).execute()
    recent = []
    for r in recent_res.data:
        ev = r.pop('events')
        if isinstance(ev, list):
            ev = ev[0]
        r['event_name'] = ev['event_name']
        recent.append(r)
        
    return {
        'total_events': events_c or 0,
        'total_photos': photos_c or 0,
        'total_faces': faces_c or 0,
        'total_searches': searches_c or 0,
        'storage_mb': 0.0, # Cloud storage is practically unlimited
        'recent_searches': recent
    }
