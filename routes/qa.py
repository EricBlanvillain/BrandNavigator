import logging
from flask import Blueprint, request, jsonify, session, current_app
# Note: Assuming agents will be attached to the app object in app.py
# from agents.qa import QAAgent - Not needed here if accessed via current_app

qa_bp = Blueprint('qa', __name__)

logger = logging.getLogger(__name__) # Or use current_app.logger within routes

# --- NEW QA Endpoint ---
@qa_bp.route('/qa', methods=['POST'])
def qa_endpoint():
    """API endpoint to handle follow-up questions.
       Uses the context stored from the user's session.
       Returns JSON with either 'answer' or an 'error'."""

    # +++ Debugging incoming QA request +++
    current_app.logger.debug(f"QA Request Headers: {request.headers}")
    current_app.logger.debug(f"QA Request Content-Type: {request.content_type}")
    current_app.logger.debug(f"QA Request Raw Data: {request.data}")
    current_app.logger.debug(f"QA Request Form Dict: {request.form.to_dict()}")
    current_app.logger.debug(f"QA Request Values Dict: {request.values.to_dict()}")
    # +++++++++++++++++++++++++++++++++++++++

    # Try reading from request.values which combines form and args
    question = request.values.get('question')

    if not question:
        current_app.logger.error("Failed to find 'question' field in request values.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Missing Input',
            'details': 'No question provided in the request.'
        }), 400

    # Retrieve context from session
    research_data = session.get('research_data')
    evaluation_data = session.get('evaluation_data')
    analyzed_brand = session.get('analyzed_brand')

    # Access agent via current_app
    qa_agent = getattr(current_app, 'qa_agent', None)

    # Check if QA agent is available
    if not qa_agent or not qa_agent.client:
        current_app.logger.error("QA Agent not available for follow-up question.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Service Initialization Error',
            'details': 'The QA service agent failed to initialize or is unavailable.'
        }), 503

    # Check if context exists
    if not research_data:
        current_app.logger.warning("QA request received, but no analysis context found in session.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Missing Context',
            'details': 'Please perform an initial analysis first before asking follow-up questions.'
        }), 400

    current_app.logger.info(f"Received QA request: '{question}' for analyzed brand: {analyzed_brand}")
    try:
        # Call the QA agent
        qa_result = qa_agent.answer_followup(
            question=question,
            research_data=research_data,
            evaluation_data=evaluation_data
        )

        # Handle potential errors or successful response dictionary from QA agent
        if isinstance(qa_result, dict):
            if qa_result.get("error"):
                error_detail = qa_result.get("error")
                current_app.logger.error(f"QA agent returned an error: {error_detail}")
                return jsonify({
                    'success': False,
                    'error': 'QA Processing Error',
                    'details': error_detail
                }), 500
            elif qa_result.get("answer"):
                # Success - extract the answer string
                answer_text = qa_result.get("answer")
                current_app.logger.info(f"QA agent provided answer successfully.")
                return jsonify({
                    'success': True,
                    'answer': answer_text # Return just the string
                })
            else:
                # Dictionary format, but missing expected keys
                current_app.logger.error(f"QA agent returned a dictionary with unexpected keys: {qa_result.keys()}")
                return jsonify({
                    'success': False,
                    'error': 'QA Processing Error',
                    'details': 'Received an invalid response format (unexpected dictionary) from the QA agent.'
                }), 500
        else:
             # Not a dictionary, unexpected format (e.g., None, list, etc.)
             current_app.logger.error(f"QA agent returned an unexpected format (not dict): {type(qa_result)}")
             return jsonify({
                 'success': False,
                 'error': 'QA Processing Error',
                 'details': 'Received an invalid response format from the QA agent.'
             }), 500

    except Exception as e:
        # Catch-all for unexpected errors during QA processing
        current_app.logger.exception(f"Unhandled exception during /qa endpoint for question '{question}': {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error', # More generic user message
            'details': 'An unexpected error occurred during the QA process. Please check server logs.'
        }), 500
