from flask import Flask
from flask_cors import CORS
from .database import init_db
from .routes import api

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    init_db(app)
    app.register_blueprint(api, url_prefix='/api')
    
    @app.route('/')
    def index():
        return "PatientAgent Backend is running! The API is at /api and the frontend dashboard is at http://localhost:8080"
    
    import threading
    import time
    from .services import PatientService
    
    def background_watcher():
        while True:
            time.sleep(60) # Check every 60 seconds
            with app.app_context():
                PatientService.check_idle_conversations()

    # Start the background thread
    watcher_thread = threading.Thread(target=background_watcher, daemon=True)
    watcher_thread.start()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
