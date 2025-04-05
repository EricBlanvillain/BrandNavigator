import logging
from flask import Blueprint, render_template, request, jsonify, session, current_app
from markupsafe import Markup
# Note: Assuming agents will be attached to the app object in app.py
# from agents.orchestrator import OrchestratorAgent - Not needed here if accessed via current_app

analysis_bp = Blueprint('analysis', __name__, template_folder='../templates', static_folder='../static') # Adjust paths relative to blueprint

logger = logging.getLogger(__name__) # Or use current_app.logger within routes

@analysis_bp.route('/', methods=['GET'])
def index():
    """Renders the main landing page."""
    return render_template('index.html')

@analysis_bp.route('/analyze', methods=['POST'])
def analyze_endpoint():
    """API endpoint to handle the brand name analysis.
       Calls agents via orchestrator attributes, stores context, and returns structured data.
    """
    session.pop('research_data', None)
    session.pop('evaluation_data', None)
    session.pop('analyzed_brand', None)

    brand_name = request.form.get('brand_name')
    if not brand_name:
        current_app.logger.warning("Received analyze request with no brand name.")
        return jsonify({'success': False, 'error': 'Missing Input', 'details': 'Please enter a brand name to analyze.'}), 400

    orchestrator = getattr(current_app, 'orchestrator', None)
    if not orchestrator or not orchestrator.market_researcher or not orchestrator.evaluator or not orchestrator.reporter:
         current_app.logger.error("Orchestrator or its agents not available for analysis request.")
         return jsonify({
             'success': False,
             'error': 'Service Initialization Error',
             'details': 'Core analysis agents failed to initialize. Please check server logs.'
         }), 503

    current_app.logger.info(f"Received API request to analyze brand: {brand_name}")
    try:
        # --- 1. Call Market Researcher ---
        current_app.logger.info(f"Calling market_researcher.research for: {brand_name}")
        research_results = orchestrator.market_researcher.research(brand_name)
        # Check for critical research errors
        if not isinstance(research_results, dict) or research_results.get("error") == "Invalid base domain generated":
            error_detail = research_results.get('error', 'Invalid data format') if isinstance(research_results, dict) else 'Invalid data format'
            current_app.logger.error(f"Market research failed critically: {error_detail}")
            return jsonify({
                'success': False,
                'error': 'Market Research Failed',
                'details': error_detail
            }), 500
        current_app.logger.info(f"Market research completed for: {brand_name}")

        # --- 2. Call Evaluator ---
        evaluation_results = None
        if orchestrator.evaluator.client: # Check if evaluator is ready (has client)
            current_app.logger.info(f"Calling evaluator.evaluate for: {brand_name}")
            evaluation_results = orchestrator.evaluator.evaluate(brand_name, research_results)
            if isinstance(evaluation_results, dict) and evaluation_results.get("error"):
                current_app.logger.error(f"Evaluation agent returned an error: {evaluation_results.get('error')}")
                # Keep the error, don't fail the whole request yet
            else:
                 current_app.logger.info(f"Evaluation completed for: {brand_name}")
        else:
            current_app.logger.warning("Evaluation skipped: Evaluator client not initialized.")
            evaluation_results = {"error": "Evaluation skipped: Agent not initialized"}

        # --- 3. Generate Report ---
        markdown_report = ""
        try:
            current_app.logger.info(f"Calling reporter.generate_report for: {brand_name}")
            markdown_report = orchestrator.reporter.generate_report(
                brand_name=brand_name,
                research_data=research_results,
                evaluation_data=evaluation_results,
                output_format='markdown'
            )
            if not isinstance(markdown_report, str):
                logger.error(f"Reporter returned non-string: {type(markdown_report)}")
                markdown_report = "*Error generating report summary.*"
        except Exception as report_err:
             logger.exception(f"Error during report generation: {report_err}")
             markdown_report = f"*Error during report generation: {report_err}*"

        # --- Store context in session ---
        session['research_data'] = research_results
        session['evaluation_data'] = evaluation_results
        session['analyzed_brand'] = brand_name
        session.modified = True
        current_app.logger.info(f"Stored analysis context in session for brand: {brand_name}")

        # --- Return combined response ---
        return jsonify({
            'success': True,
            'brand_name': brand_name,
            'research_data': research_results,
            'evaluation_data': evaluation_results,
            'report_markdown': markdown_report
        })

    except Exception as e:
        current_app.logger.exception(f"Unhandled exception during /analyze endpoint for {brand_name}: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'details': f'An unexpected error occurred in the endpoint handler: {str(e)}'
        }), 500
