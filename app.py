# brand_navigator/app.py

import os
import logging
# Removed markdown, request, jsonify, render_template, Markup imports as they are now in blueprints
from flask import Flask, session # Keep session import if used outside blueprints, or remove if only used within
from dotenv import load_dotenv
from flask_session import Session

# Import our agent orchestrator
from agents.orchestrator import OrchestratorAgent
# Removed EvaluatorAgent import as it's likely used within Orchestrator
from agents.qa import QAAgent

# --- Import Blueprints ---
from routes.analysis import analysis_bp
from routes.qa import qa_bp
from routes.settings import settings_bp # Import the new settings blueprint


# --- Configuration & Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file located in the *brand_navigator* directory
# Assuming the app is run from the project root (one level above brand_navigator)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env') # Looks for .env inside brand_navigator
alt_dotenv_path = '.env' # If .env is in project root instead

# Try loading from brand_navigator first, then project root
loaded_env = load_dotenv(dotenv_path=dotenv_path, override=True)
if not loaded_env:
    logger.info(f"Did not find .env in {dotenv_path}, trying project root {alt_dotenv_path}...")
    loaded_env = load_dotenv(dotenv_path=alt_dotenv_path, override=True)

if loaded_env:
    logger.info("Successfully loaded .env file.")
else:
    logger.warning("Could not find .env file in standard locations. API keys might be missing.")

# --- Flask App Initialization ---
# Note: Removed template_folder and static_folder here as they are defined in the analysis_bp
app = Flask(__name__)
app.logger.setLevel(logging.DEBUG) # <-- Set logger level to DEBUG

# --- Configure Flask-Session ---
# Load SECRET_KEY from environment or use a default (change for production!)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_default_development_secret_key')
if app.config['SECRET_KEY'] == 'a_default_development_secret_key':
    logger.warning("Using default SECRET_KEY. Set FLASK_SECRET_KEY environment variable for production!")

# Configure session type to filesystem (stores sessions in a 'flask_session' folder)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False # Session expires when browser closes
app.config['SESSION_USE_SIGNER'] = True # Encrypts the session cookie
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_session')

# Ensure the session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Initialize the Session extension
Session(app)
# ------------------------------

# --- Initialize Agents ---
# Store agents directly on the app object for access via current_app in blueprints
try:
    app.orchestrator = OrchestratorAgent()
    app.qa_agent = QAAgent()
    logger.info("OrchestratorAgent and QAAgent initialized successfully and attached to app.")
except Exception as e:
    logger.exception(f"CRITICAL: Failed to initialize agents: {e}. Check API keys/agent code.")
    app.orchestrator = None
    app.qa_agent = None

# --- Register Blueprints ---
app.register_blueprint(analysis_bp)
app.register_blueprint(qa_bp)
app.register_blueprint(settings_bp) # Register the settings blueprint

# --- Removed Global variable for context ---
# --- Removed Routes --- (Moved to blueprints)


# --- Main Execution (Optional, as Flask CLI is preferred) ---
if __name__ == '__main__':
    # Note: Use 'flask run' command instead for development server
    # Add debug=True only for development, remove or set to False for production
    app.run(debug=os.getenv('FLASK_ENV') == 'development')
