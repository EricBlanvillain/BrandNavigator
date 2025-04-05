# brand_navigator/app.py

import os
import logging
import markdown
from flask import Flask, render_template, request, jsonify
from markupsafe import Markup
from dotenv import load_dotenv

# Import our agent orchestrator
from brand_navigator.agents.orchestrator import OrchestratorAgent
from brand_navigator.agents.evaluator import EvaluatorAgent
from brand_navigator.agents.qa import QAAgent

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
# Consider adding a secret key for session management if needed later
# app.secret_key = os.urandom(24)

# --- Initialize Agents ---
try:
    orchestrator = OrchestratorAgent()
    qa_agent = QAAgent()
    logger.info("OrchestratorAgent and QAAgent initialized successfully.")
except Exception as e:
    logger.exception(f"CRITICAL: Failed to initialize agents: {e}. Check API keys/agent code.")
    orchestrator = None
    qa_agent = None

# --- Global variable for context (SIMPLE APPROACH - NOT SUITABLE FOR PRODUCTION) ---
last_analysis_context = {
    "research_data": None,
    "evaluation_data": None
}

# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main landing page."""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_endpoint():
    """API endpoint to handle the brand name analysis.
       Returns JSON with either 'html' content or an 'error'.
       Stores context on success.
    """
    global last_analysis_context # Declare intent to modify global
    last_analysis_context = {"research_data": None, "evaluation_data": None} # Clear previous context

    brand_name = request.form.get('brand_name')

    if not brand_name:
        logger.warning("Received analyze request with no brand name.")
        return jsonify({'error': 'Please enter a brand name to analyze.'}), 400 # Bad Request

    if not orchestrator:
         logger.error("Orchestrator not available for analysis request.")
         return jsonify({'error': 'Analysis service is currently unavailable due to an initialization error.'}), 503 # Service Unavailable

    logger.info(f"Received API request to analyze brand: {brand_name}")
    try:
        # Run analysis - NOTE: Orchestrator no longer runs QA by default
        # For the purpose of QA context, we need both research and eval results separately

        # 1. Get Research Data
        research_results = orchestrator.market_researcher.research(brand_name)
        if not research_results or research_results.get("error") == "Invalid base domain generated":
            logger.error(f"Market research failed critically: {research_results.get('error')}")
            return jsonify({"error": f"Market research failed: {research_results.get('error')}"}), 500

        # 2. Get Evaluation Data
        evaluation_results = None
        if orchestrator.evaluator and orchestrator.evaluator.client:
            evaluation_results = orchestrator.evaluator.evaluate(brand_name, research_results)
            if evaluation_results.get("error"):
                logger.error(f"Evaluation step failed but continuing: {evaluation_results['error']}")
        else:
            evaluation_results = {"error": "Evaluation skipped: Agent not initialized"}

        # 3. Generate Report (using the reporter within orchestrator instance)
        markdown_report = orchestrator.reporter.generate_report(
            brand_name=brand_name,
            research_data=research_results,
            evaluation_data=evaluation_results,
            output_format='markdown'
        )

        if not isinstance(markdown_report, str):
            error_msg = evaluation_results.get('error', 'Unknown report generation error')
            logger.error(f"Report generation failed: {error_msg}")
            return jsonify({"error": f"Report generation failed: {error_msg}"}), 500

        # --- Store context on successful analysis ---
        last_analysis_context["research_data"] = research_results
        last_analysis_context["evaluation_data"] = evaluation_results
        logger.info(f"Stored analysis context for brand: {brand_name}")
        # ---------------------------------------------

        # Convert final markdown report to HTML
        report_html = markdown.markdown(markdown_report, extensions=['fenced_code', 'tables', 'nl2br'])
        return jsonify({'html': report_html})

    except Exception as e:
        logger.exception(f"Unhandled exception during /analyze endpoint for {brand_name}: {e}")
        return jsonify({'error': 'A critical server error occurred while processing your request.'}), 500

# --- NEW QA Endpoint ---
@app.route('/qa', methods=['POST'])
def qa_endpoint():
    """API endpoint to handle follow-up questions.
       Uses the context stored from the last analysis.
       Returns JSON with either 'answer' or an 'error'."""
    global last_analysis_context # Access the stored context

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
        logger.error("Failed to find 'question' field in request values.") # Add specific log
        return jsonify({'error': 'No question provided.'}), 400

    # Check if QA agent is available
    if not qa_agent or not qa_agent.client:
        logger.error("QA Agent not available for follow-up question.")
        return jsonify({'error': 'QA service is currently unavailable.'}), 503

    # Check if context from a previous analysis exists
    if not last_analysis_context["research_data"]:
        logger.warning("Received QA request but no analysis context found.")
        return jsonify({'error': 'Please perform an initial analysis first before asking follow-up questions.'}), 400

    logger.info(f"Received QA request: '{question}'")
    try:
        # Call the QA agent's answer method with the stored context
        qa_result = qa_agent.answer_followup(
            question=question,
            research_data=last_analysis_context["research_data"],
            evaluation_data=last_analysis_context["evaluation_data"]
        )

        if 'error' in qa_result:
            # Error occurred during QA processing
            logger.error(f"QA agent returned an error: {qa_result['error']}")
            return jsonify({'error': qa_result['error']}), 500
        else:
            # Success, return the answer
            logger.info("QA agent provided answer successfully.")
            return jsonify({'answer': qa_result.get('answer', 'No answer generated.')})

    except Exception as e:
        logger.exception(f"Unhandled exception during /qa endpoint for question '{question}': {e}")
        return jsonify({'error': 'A critical server error occurred while answering the question.'}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Runs the Flask development server
    # Debug mode should be False in production
    app.run(debug=True, port=5001)
