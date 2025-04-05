import pytest
import os
# from brand_navigator.app import app as flask_app # Import your Flask app instance
from app import app as flask_app # Import directly from app.py in the root

# Ensure we use a testing configuration
# We might want a separate config file later, but for now, we override keys
flask_app.config.update({
    "TESTING": True,
    "SECRET_KEY": "testing_secret_key", # Use a fixed key for tests
    "SESSION_TYPE": "filesystem", # Use filesystem for tests too, or 'redis' if configured
    "SESSION_FILE_DIR": os.path.join(os.path.dirname(__file__), '_test_flask_session'), # Test-specific session dir
    # Suppress WTForms CSRF protection if you were using Flask-WTF
    # "WTF_CSRF_ENABLED": False,
})

# Ensure the test session directory exists
os.makedirs(flask_app.config['SESSION_FILE_DIR'], exist_ok=True)

@pytest.fixture(scope='module')
def app():
    """Fixture to provide the Flask app instance."""
    yield flask_app

@pytest.fixture(scope='module')
def client(app):
    """Fixture to provide a test client for the Flask app."""
    return app.test_client()

# Clean up test session files after tests run (optional but good practice)
# You might need more sophisticated cleanup depending on test structure
# @pytest.fixture(autouse=True, scope='session')
# def cleanup_test_sessions():
#     yield
#     # Code here runs after all tests in the session
#     session_dir = flask_app.config['SESSION_FILE_DIR']
#     if os.path.exists(session_dir):
#         import shutil
#         # print(f"\nCleaning up test session directory: {session_dir}")
#         # Be careful with recursive deletion!
#         # shutil.rmtree(session_dir)

# Add any other shared fixtures here, e.g., for database setup/teardown if needed
