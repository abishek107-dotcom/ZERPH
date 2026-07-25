import os
import socket
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Vercel Serverless Temp Folder
TEMP_FOLDER = '/tmp'

# Secure Admin Authentication Settings
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', '_abishekvox')
# Password hash for 'Abishek@107' using Werkzeug PBKDF2:SHA256
ADMIN_PASSWORD_HASH = os.environ.get('ADMIN_PASSWORD_HASH', generate_password_hash('Abishek@107'))

# Security Rate Limiting
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_TIME_SECONDS = 300  # 5 minutes lockout after 5 failed attempts

# Face Engine Thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.62  # Used for local but Face++ returns 0-100 score
FACEPP_CONFIDENCE_THRESHOLD = 75.0   # Face++ Compare API threshold
MAX_SELFIE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# ---------------------------------------------------------
# CLOUD INTEGRATIONS (Environment Variables for Vercel)
# ---------------------------------------------------------
# Supabase
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Cloudinary
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

# Face++ API
FACEPP_API_KEY = os.environ.get('FACEPP_API_KEY', '')
FACEPP_API_SECRET = os.environ.get('FACEPP_API_SECRET', '')

def get_local_ip():
    """Find the local IP address of the server for LAN access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# On Vercel, the host provided is usually a custom domain or vercel.app
SERVER_IP = os.environ.get('VERCEL_URL', get_local_ip())
PORT = 5000
