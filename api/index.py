import os
import sys

# Ensure root directory is on Python path so app.py and templates are found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
