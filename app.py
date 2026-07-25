import os
import uuid
import time
import io
import zipfile
import qrcode
import requests
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, session
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

import cloudinary
import cloudinary.uploader

import config
from database import (
    init_db, add_event, get_event, get_all_events, delete_event,
    add_image, add_face, get_faces_by_event, log_search, get_dashboard_stats
)
from face_engine import face_engine

app = Flask(__name__, 
            template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates')),
            static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), 'static')))
app.config['SECRET_KEY'] = 'smart-event-photo-retrieval-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max batch size

# Initialize Cloudinary
if config.CLOUDINARY_CLOUD_NAME:
    cloudinary.config(
        cloud_name = config.CLOUDINARY_CLOUD_NAME,
        api_key = config.CLOUDINARY_API_KEY,
        api_secret = config.CLOUDINARY_API_SECRET,
        secure = True
    )

# Security Rate Limiting Tracking Dictionary {ip: {'attempts': int, 'lockout_until': float}}
FAILED_LOGIN_ATTEMPTS = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

# Login Required Decorator for Admin Security
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------
# Admin Authentication & Security Routes
# ---------------------------------------------------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))
        
    client_ip = request.remote_addr or '127.0.0.1'
    now = time.time()
    
    # Check brute force lockout
    if client_ip in FAILED_LOGIN_ATTEMPTS:
        attempt_data = FAILED_LOGIN_ATTEMPTS[client_ip]
        if attempt_data['attempts'] >= config.MAX_LOGIN_ATTEMPTS:
            remaining_lockout = int(attempt_data['lockout_until'] - now)
            if remaining_lockout > 0:
                return render_template(
                    'admin_login.html', 
                    error=f"Too many failed login attempts. Security lockout active for {remaining_lockout} seconds."
                )
            else:
                FAILED_LOGIN_ATTEMPTS[client_ip] = {'attempts': 0, 'lockout_until': 0}

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Verify credentials securely with password hash check
        if username == config.ADMIN_USERNAME and check_password_hash(config.ADMIN_PASSWORD_HASH, password):
            FAILED_LOGIN_ATTEMPTS.pop(client_ip, None)
            session['logged_in'] = True
            session['admin_user'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            if client_ip not in FAILED_LOGIN_ATTEMPTS:
                FAILED_LOGIN_ATTEMPTS[client_ip] = {'attempts': 1, 'lockout_until': 0}
            else:
                FAILED_LOGIN_ATTEMPTS[client_ip]['attempts'] += 1
                
            attempts = FAILED_LOGIN_ATTEMPTS[client_ip]['attempts']
            if attempts >= config.MAX_LOGIN_ATTEMPTS:
                FAILED_LOGIN_ATTEMPTS[client_ip]['lockout_until'] = now + config.LOCKOUT_TIME_SECONDS
                error_msg = "Maximum security login attempts exceeded. Account locked for 5 minutes."
            else:
                error_msg = f"Invalid admin credentials. {config.MAX_LOGIN_ATTEMPTS - attempts} attempt(s) remaining."
                
            return render_template('admin_login.html', error=error_msg)
            
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

# ---------------------------------------------------------
# 1. ADMIN PANEL APPLICATION (Protected Administrative Suite)
# ---------------------------------------------------------

@app.route('/')
@app.route('/admin')
@login_required
def admin_dashboard():
    stats = get_dashboard_stats()
    events = get_all_events()
    return render_template('admin_dashboard.html', stats=stats, events=events, server_ip=config.SERVER_IP, port=config.PORT)

@app.route('/admin/events/new', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        event_name = request.form.get('event_name')
        date = request.form.get('date')
        venue = request.form.get('venue')
        description = request.form.get('description', '')
        
        if not event_name or not date or not venue:
            return render_template('create_event.html', error="Please fill out all required fields.")
            
        event_id = str(uuid.uuid4())[:8]
        
        qr_data = f"http://{config.SERVER_IP}/event/{event_id}"
        if ':' in config.SERVER_IP: # simple check for port if running locally
             pass
        elif not config.SERVER_IP.startswith('http'):
            # Vercel URL
            qr_data = f"https://{config.SERVER_IP}/event/{event_id}"
        
        # Generate QR Code Image
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(qr_data)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="#000000", back_color="#ffffff")
        
        # Save to memory instead of /tmp to avoid filesystem issues
        img_byte_arr = io.BytesIO()
        img_qr.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        
        qr_url = ""
        if config.CLOUDINARY_CLOUD_NAME:
            try:
                upload_result = cloudinary.uploader.upload(img_byte_arr, folder="smart_event/qrcodes")
                qr_url = upload_result.get('secure_url', '')
            except Exception as e:
                print(f"Cloudinary QR Upload Error: {e}")
        
        # Create Face++ FaceSet
        face_engine.create_faceset(event_id)
        
        add_event(event_id, event_name, date, venue, description, qr_url)
        return redirect(url_for('upload_photos', event_id=event_id))
        
    return render_template('create_event.html')

@app.route('/admin/events/<event_id>/upload', methods=['GET', 'POST'])
@login_required
def upload_photos(event_id):
    event = get_event(event_id)
    if not event:
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        files = request.files.getlist('photos')
        if not files or files[0].filename == '':
            return jsonify({'error': 'No photographs selected for upload.'}), 400
            
        uploaded_count = 0
        total_faces_detected = 0
        
        for file in files:
            if file and allowed_file(file.filename):
                image_id = str(uuid.uuid4())[:12]
                
                try:
                    # Cloudinary Upload
                    if config.CLOUDINARY_CLOUD_NAME:
                        file.seek(0)
                        upload_res = cloudinary.uploader.upload(file, folder=f"smart_event/events/{event_id}")
                        image_url = upload_res.get('secure_url')
                    else:
                        image_url = "placeholder_url"
                    
                    add_image(image_id, event_id, image_url, secure_filename(file.filename))
                    uploaded_count += 1
                    
                    # Run AI Face Engine Detection
                    detected_faces = face_engine.detect_faces(image_url)
                    for face_data in detected_faces:
                        face_id = str(uuid.uuid4())[:12]
                        face_token = face_data['face_token']
                        
                        add_face(
                            face_id=face_id,
                            image_id=image_id,
                            event_id=event_id,
                            embedding_vector=[], # Face++ handles embedding via token
                            face_token=face_token,
                            bounding_box=face_data['bbox'],
                            confidence=face_data['confidence']
                        )
                        
                        # Add token to event FaceSet
                        face_engine.add_face_to_faceset(event_id, face_token)
                        total_faces_detected += 1
                except Exception as e:
                    print(f"Error processing upload: {e}")
                    return jsonify({'error': f"Failed to process {file.filename}: {str(e)}"}), 500
                    
        return jsonify({
            'success': True,
            'uploaded_images': uploaded_count,
            'faces_detected': total_faces_detected,
            'event_id': event_id
        })
        
    return render_template('upload_photos.html', event=event)

@app.route('/admin/events/<event_id>/delete', methods=['POST'])
@login_required
def delete_event_route(event_id):
    face_engine.delete_faceset(event_id)
    success = delete_event(event_id)
    return jsonify({'success': success})

# ---------------------------------------------------------
# 2. USER SCAN APPLICATION (Public Live Face Scanner Portal)
# ---------------------------------------------------------

@app.route('/scan')
def user_scan_portal():
    events = get_all_events()
    return render_template('scan_select.html', events=events)

@app.route('/event/<event_id>')
def participant_portal(event_id):
    event = get_event(event_id)
    if not event:
        return render_template('error.html', message="Event not found or has been removed."), 404
    return render_template('participant_search.html', event=event)

@app.route('/api/search', methods=['POST'])
def search_photos():
    start_time = time.time()
    
    event_id = request.form.get('event_id')
    # Threshold is not actively used for Face++ search in the same way as local, Face++ uses its own.
    
    if 'selfie' not in request.files:
        return jsonify({'error': 'No live face camera capture provided.'}), 400
        
    file = request.files['selfie']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid face image format.'}), 400
        
    event = get_event(event_id)
    if not event:
        return jsonify({'error': 'Event not found.'}), 404
        
    try:
        stored_faces = get_faces_by_event(event_id)
        if not stored_faces:
            return jsonify({
                'matches': [],
                'total_matches': 0,
                'message': 'No photographs have been uploaded for this event yet.'
            })
            
        # Pass the file directly to face_engine in memory
        file.seek(0)
        result = face_engine.match_selfie_against_event(file, event_id, stored_faces=stored_faces)
        
        if 'error' in result:
             return jsonify({'error': result['error']}), 500
             
        matched_list = result.get('matches', [])
        processing_time_ms = round((time.time() - start_time) * 1000, 2)
        
        search_id = str(uuid.uuid4())[:10]
        log_search(search_id, event_id, len(matched_list), processing_time_ms)
        
        return jsonify({
            'success': True,
            'matches': matched_list,
            'total_matches': len(matched_list),
            'processing_time_ms': processing_time_ms,
            'threshold_used': config.FACEPP_CONFIDENCE_THRESHOLD
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download_zip', methods=['POST'])
def download_zip():
    data = request.get_json()
    image_paths = data.get('image_paths', [])
    
    if not image_paths:
        return jsonify({'error': 'No images selected for zip download.'}), 400
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, img_url in enumerate(image_paths):
            try:
                # Fetch image from Cloudinary URL
                resp = requests.get(img_url, timeout=10)
                if resp.status_code == 200:
                    ext = img_url.split('.')[-1]
                    if len(ext) > 4: ext = 'jpg'
                    filename = f"event_photo_{idx+1}.{ext}"
                    zf.writestr(filename, resp.content)
            except Exception as e:
                print(f"Failed to download {img_url} for zip: {e}")
                
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='my_event_photos.zip'
    )

if __name__ == '__main__':
    print("=" * 65)
    print(" AI-Based Smart Event Photo Retrieval System (Vercel Ready)")
    print(f" * Admin Username: {config.ADMIN_USERNAME}")
    print(" * Admin Security: Werkzeug Hashed PBKDF2:SHA256 (Protected)")
    print(f" * 1. Admin Panel URL:   http://127.0.0.1:{config.PORT}/admin")
    print(f" * 2. User Scan URL:     http://{config.SERVER_IP}:{config.PORT}/scan")
    print("=" * 65)
    app.run(host='0.0.0.0', port=config.PORT, debug=True)
