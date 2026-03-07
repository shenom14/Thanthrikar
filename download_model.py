import urllib.request
import zipfile
import os
import sys

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
ZIP_PATH = "vosk-model.zip"
EXTRACT_DIR = "backend/model"

print("Downloading Vosk model...")
urllib.request.urlretrieve(MODEL_URL, ZIP_PATH)

print("Extracting...")
with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
    zip_ref.extractall("backend")

# Rename extracted folder to standard "model" format
os.rename("backend/vosk-model-small-en-us-0.15", EXTRACT_DIR)
os.remove(ZIP_PATH)

print("Vosk model ready at:", EXTRACT_DIR)
