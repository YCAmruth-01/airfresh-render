# Airfresh Backend

A Flask-based backend service for the Airfresh application.

## Project Structure

```
airfresh-backend/
├── main.py           # Flask application entry point
├── requirements.txt  # Python dependencies
├── render.yaml       # Render deployment configuration
├── .env.example      # Environment variables template
├── .gitignore        # Git ignore rules
├── venv/             # Python virtual environment
└── static/
    └── index.html    # Frontend dashboard
```

## Setup & Installation

### Prerequisites
- Python 3.11+
- pip

### Steps

1. **Clone or navigate to the project:**
   ```bash
   cd airfresh-backend
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create environment file:**
   ```bash
   cp .env.example .env
   ```

5. **Run the application:**
   ```bash
   python main.py
   ```

The application will be available at `http://localhost:5000`

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/status` - Application status
- `GET /api/health` - Health check endpoint

## Deployment

### Render Deployment

The project includes `render.yaml` for deployment on Render.

1. Push code to Git repository
2. Connect repository to Render
3. Render will automatically detect and deploy using the configuration in `render.yaml`

### Local Server

For production on your machine:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

## Environment Variables

- `PORT` - Server port (default: 5000)
- `FLASK_ENV` - Environment type (development/production)
- `FLASK_DEBUG` - Debug mode (True/False)

## Dependencies

- **Flask** - Web framework
- **Werkzeug** - WSGI utility library
- **Gunicorn** - WSGI HTTP Server
- **python-dotenv** - Environment variable loader
