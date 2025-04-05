# brand_navigator/app.py

import os
import logging
import markdown
from flask import Flask, render_template, request, jsonify, session
from markupsafe import Markup
from dotenv import load_dotenv
from flask_session import Session

# Import our agent orchestrator
from agents.orchestrator import OrchestratorAgent
from agents.evaluator import EvaluatorAgent
from agents.qa import QAAgent

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
app = Flask(__name__, template_folder='templates', static_folder='static')
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
try:
    orchestrator = OrchestratorAgent()
    qa_agent = QAAgent()
    logger.info("OrchestratorAgent and QAAgent initialized successfully.")
except Exception as e:
    logger.exception(f"CRITICAL: Failed to initialize agents: {e}. Check API keys/agent code.")
    orchestrator = None
    qa_agent = None

# --- Global variable for context (REMOVED) ---
# last_analysis_context = {
#     "research_data": None,
#     "evaluation_data": None
# }

# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main landing page."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    """API endpoint to handle the brand name analysis.
       Returns JSON with structured analysis data or an error.
       Stores context in the user's session on success.
    """
    # Clear previous analysis context from session
    session.pop('research_data', None)
    session.pop('evaluation_data', None)
    session.pop('analyzed_brand', None) # Also clear the brand name

    brand_name = request.form.get('brand_name')

    if not brand_name:
        logger.warning("Received analyze request with no brand name.")
        return jsonify({'success': False, 'error': 'Missing Input', 'details': 'Please enter a brand name to analyze.'}), 400

    if not orchestrator:
         logger.error("Orchestrator not available for analysis request.")
         return jsonify({
             'success': False,
             'error': 'Service Initialization Error',
             'details': 'The analysis service orchestrator failed to initialize. Please check server logs.'
         }), 503

    logger.info(f"Received API request to analyze brand: {brand_name}")
    try:
        # 1. Get Research Data
        research_results = orchestrator.market_researcher.research(brand_name)
        if isinstance(research_results, dict) and research_results.get("error"):
            error_detail = research_results.get('error')
            logger.error(f"Market research agent returned an error: {error_detail}")
            # Return structured error based on agent's feedback
            return jsonify({
                'success': False,
                'error': 'Market Research Failed',
                'details': error_detail # Pass agent's error message as details
            }), 500
        elif not research_results:
             logger.error(f"Market research returned no results or an unexpected format for {brand_name}")
             return jsonify({
                'success': False,
                'error': 'Market Research Failed',
                'details': 'Received no valid data from the market research agent.'
             }), 500

        # 2. Get Evaluation Data
        evaluation_results = None
        eval_error_detail = None
        if orchestrator.evaluator and orchestrator.evaluator.client:
            evaluation_results = orchestrator.evaluator.evaluate(brand_name, research_results)
            if isinstance(evaluation_results, dict) and evaluation_results.get("error"):
                eval_error_detail = evaluation_results.get('error')
                logger.error(f"Evaluation agent returned an error: {eval_error_detail}")
                # Store the error but continue to report generation
                evaluation_results = {"error": eval_error_detail} # Keep error info for report
        else:
            eval_error_detail = "Evaluation agent not initialized or available."
            logger.warning(eval_error_detail)
            evaluation_results = {"error": eval_error_detail}

        # 3. Generate Report
        markdown_report = orchestrator.reporter.generate_report(
            brand_name=brand_name,
            research_data=research_results,
            evaluation_data=evaluation_results, # Pass potential error dict here
            output_format='markdown'
        )

        # Check if report generation itself failed (e.g., returned None or a dict with error)
        report_error_detail = None
        if not isinstance(markdown_report, str):
            if isinstance(markdown_report, dict) and markdown_report.get('error'):
                report_error_detail = markdown_report.get('error')
            else:
                report_error_detail = 'Report generator returned an invalid format.'
            logger.error(f"Report generation failed: {report_error_detail}")
            # Return structured error
            return jsonify({
                'success': False,
                'error': 'Report Generation Failed',
                'details': report_error_detail
            }), 500

        # --- Store context in session on successful analysis ---
        # Note: We store results even if evaluation had an error, context is needed for QA
        session['research_data'] = research_results
        session['evaluation_data'] = evaluation_results # Store evaluation result/error
        session['analyzed_brand'] = brand_name
        session.modified = True
        logger.info(f"Stored analysis context in session for brand: {brand_name}")

        # Return structured success response (report might mention eval error)
        return jsonify({
            'success': True,
            'brand_name': brand_name,
            'research_data': research_results,
            'evaluation_data': evaluation_results,
            'report_markdown': markdown_report
        })

    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unhandled exception during /analyze endpoint for {brand_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error', # More generic user message
            'details': 'An unexpected error occurred. Please check server logs for details.'
        }), 500

# --- NEW QA Endpoint ---
@app.route('/qa', methods=['POST'])
def qa_endpoint():
    """API endpoint to handle follow-up questions.
       Uses the context stored from the user's session.
       Returns JSON with either 'answer' or an 'error'."""
    # Remove global access: global last_analysis_context

    # +++ Debugging incoming QA request +++
    logger.debug(f"QA Request Headers: {request.headers}")
    logger.debug(f"QA Request Content-Type: {request.content_type}")
    logger.debug(f"QA Request Raw Data: {request.data}")
    logger.debug(f"QA Request Form Dict: {request.form.to_dict()}")
    logger.debug(f"QA Request Values Dict: {request.values.to_dict()}")
    # +++++++++++++++++++++++++++++++++++++++

    # Try reading from request.values which combines form and args
    question = request.values.get('question')

    if not question:
        logger.error("Failed to find 'question' field in request values.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Missing Input',
            'details': 'No question provided in the request.'
        }), 400

    # Retrieve context from session
    research_data = session.get('research_data')
    evaluation_data = session.get('evaluation_data')
    analyzed_brand = session.get('analyzed_brand')

    # Check if QA agent is available
    if not qa_agent or not qa_agent.client:
        logger.error("QA Agent not available for follow-up question.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Service Initialization Error',
            'details': 'The QA service agent failed to initialize or is unavailable.'
        }), 503

    # Check if context exists
    if not research_data:
        logger.warning("QA request received, but no analysis context found in session.")
        return jsonify({
            'success': False, # Add success field
            'error': 'Missing Context',
            'details': 'Please perform an initial analysis first before asking follow-up questions.'
        }), 400

    logger.info(f"Received QA request: '{question}' for analyzed brand: {analyzed_brand}")
    try:
        # Call the QA agent
        qa_result = qa_agent.answer_followup(
            question=question,
            research_data=research_data,
            evaluation_data=evaluation_data
        )

        # Check if QA agent returned an error dictionary
        if isinstance(qa_result, dict) and qa_result.get('error'):
            error_detail = qa_result['error']
            logger.error(f"QA agent returned an error: {error_detail}")
            return jsonify({
                'success': False, # Add success field
                'error': 'QA Agent Error',
                'details': error_detail
            }), 500
        elif not isinstance(qa_result, dict) or 'answer' not in qa_result:
            logger.error(f"QA agent returned an unexpected format: {qa_result}")
            return jsonify({
                'success': False,
                'error': 'QA Agent Error',
                'details': 'Received an invalid response from the QA agent.'
            }), 500
        else:
            # Success, return the answer
            logger.info("QA agent provided answer successfully.")
            # Ensure success field is present on success too for consistency
            return jsonify({
                'success': True,
                'answer': qa_result.get('answer', 'No answer generated.')
            })

    except Exception as e:
        # Catch-all for unexpected errors during QA
        logger.exception(f"Unhandled exception during /qa endpoint for question '{question}': {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error', # Generic message
            'details': 'An unexpected error occurred while answering the question. Check server logs.'
        }), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Runs the Flask development server
    # Debug mode should be False in production
    app.run(debug=True, port=5001)
