import firebase_admin
from firebase_admin import credentials
import os

# Check if Firebase app is already initialized
if not firebase_admin._apps:
    service_account_path = "firebase_service_account.json"
    
    if os.path.exists(service_account_path):
        cred = credentials.Certificate(service_account_path)
        firebase_admin.initialize_app(cred)
