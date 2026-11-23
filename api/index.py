import os
import sys

# Ensure root directory is on Python path so app.py and templates are found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel WSGI middleware to accurately map rewritten serverless paths
class VercelMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        forwarded_uri = environ.get("HTTP_X_FORWARDED_URI") or environ.get("HTTP_X_MATCHED_PATH")
        if forwarded_uri:
            environ["PATH_INFO"] = forwarded_uri.split("?")[0]
        else:
            path = environ.get("PATH_INFO", "")
            for p in ["/api/index.py", "/api/index", "/api"]:
                if path.startswith(p):
                    path = path[len(p):]
                    break
            environ["PATH_INFO"] = path if path.startswith("/") else ("/" + path)
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelMiddleware(app.wsgi_app)
