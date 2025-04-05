# brand_navigator/routes/settings.py
import os
import logging
from flask import Blueprint, request, jsonify, session, render_template, current_app

settings_bp = Blueprint('settings', __name__, template_folder='../templates')

logger = logging.getLogger(__name__)

# Route to render the settings page
@settings_bp.route('/settings', methods=['GET'])
def settings_page():
    """Renders the settings page UI."""
    return render_template('settings.html')

# API endpoint to get status and save settings
@settings_bp.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Handles getting settings status and saving API keys to session."""
    if request.method == 'POST':
        try:
            data = request.get_json()
            if not data:
                return jsonify({"success": False, "error": "Invalid request format."}), 400

            openai_key = data.get('openai_key')
            brave_key = data.get('brave_key')

            # Basic validation (presence check)
            # More specific validation (e.g., prefix check) could be added
            if openai_key and isinstance(openai_key, str):
                session['USER_OPENAI_KEY'] = openai_key
                logger.info("User OpenAI key saved to session.")
            elif 'openai_key' in data: # Handle empty string to clear key
                 session.pop('USER_OPENAI_KEY', None)
                 logger.info("User OpenAI key cleared from session.")

            if brave_key and isinstance(brave_key, str):
                session['USER_BRAVE_KEY'] = brave_key
                logger.info("User Brave key saved to session.")
            elif 'brave_key' in data: # Handle empty string to clear key
                 session.pop('USER_BRAVE_KEY', None)
                 logger.info("User Brave key cleared from session.")

            session.modified = True
            return jsonify({"success": True, "message": "Settings saved successfully."})

        except Exception as e:
            logger.exception(f"Error saving settings: {e}")
            return jsonify({"success": False, "error": f"An internal error occurred: {str(e)}"}), 500

    elif request.method == 'GET':
        # Return status indicating if keys are set in the session
        openai_set = bool(session.get('USER_OPENAI_KEY'))
        brave_set = bool(session.get('USER_BRAVE_KEY'))
        return jsonify({
            "success": True,
            "openai_key_set": openai_set,
            "brave_key_set": brave_set
        })
