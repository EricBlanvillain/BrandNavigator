# brand_navigator/agents/orchestrator.py

import logging
import os

# Import the agents we've created (and placeholders for others)
from .market_research import MarketResearchAgent
from .reporter import ReporterAgent
from .evaluator import EvaluatorAgent
from .qa import QAAgent
# from .qa import QAAgent           # TODO: Implement QAAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrchestratorAgent:
    """
    Orchestrates the workflow between different specialized agents
    for brand name analysis.
    """

    def __init__(self):
        """
        Initialize the OrchestratorAgent by creating instances of other agents.
        """
        logger.info("Initializing OrchestratorAgent...")
        self.market_researcher = MarketResearchAgent()
        self.reporter = ReporterAgent()
        self.evaluator = EvaluatorAgent()
        self.qa_agent = QAAgent()
        logger.info("OrchestratorAgent initialized with worker agents.")

    def run_analysis(self, brand_name: str, output_format: str = 'markdown') -> str | bool | None:
        """
        Executes the full brand name analysis workflow.

        Args:
            brand_name (str): The brand name to analyze.
            output_format (str): The desired format for the final report ('markdown', 'html', 'pdf').

        Returns:
            str | bool | None: The generated report content or status, depending on the format,
                               or None if an error occurs during the process.
        """
        logger.info(f"Starting analysis pipeline for brand name: '{brand_name}'")

        if not brand_name or not isinstance(brand_name, str):
            logger.error("Invalid brand name provided for analysis.")
            return None

        research_results = None
        evaluation_results = None
        report = None
        final_report = None

        try:
            # 1. Market Research
            logger.info(f"Running Market Research for '{brand_name}'...")
            research_results = self.market_researcher.research(brand_name)
            if not research_results or research_results.get("error") == "Invalid base domain generated":
                logger.error(f"Market research failed critically: {research_results.get('error')}")
                return {"error": f"Market research failed: {research_results.get('error')}"}
            logger.info(f"Market Research completed for '{brand_name}'.")

            # 2. Evaluation
            if self.evaluator and self.evaluator.client:
                logger.info(f"Running Evaluation for '{brand_name}'...")
                evaluation_results = self.evaluator.evaluate(brand_name, research_results)
                logger.info(f"Evaluation completed for '{brand_name}'.")
                if evaluation_results.get("error"):
                    logger.error(f"Evaluation step failed: {evaluation_results['error']}")
            else:
                logger.warning(f"Evaluation step skipped for '{brand_name}' (Evaluator not initialized).")
                evaluation_results = {"error": "Evaluation skipped: Agent not initialized"}

            # 3. Reporting
            logger.info(f"Generating initial report for '{brand_name}' in {output_format} format...")
            if output_format == 'markdown':
                report = self.reporter.generate_report(
                    brand_name=brand_name,
                    research_data=research_results,
                    evaluation_data=evaluation_results,
                    output_format='markdown'
                )
                logger.info(f"Initial markdown report generation complete for '{brand_name}'.")
            else:
                logger.warning(f"Skipping QA step for non-markdown format: {output_format}")
                final_report = self.reporter.generate_report(
                    brand_name=brand_name,
                    research_data=research_results,
                    evaluation_data=evaluation_results,
                    output_format=output_format
                )
                logger.info(f"Analysis pipeline finished successfully for '{brand_name}' (non-markdown report).")
                return final_report

            if not isinstance(report, str):
                 logger.error(f"Report generation failed for {brand_name}. Result: {report}")
                 if evaluation_results and evaluation_results.get('error'):
                     return {"error": f"Report generation failed, likely due to evaluation error: {evaluation_results['error']}"}
                 return {"error": "Report generation failed unexpectedly."}

            # 4. QA/Refinement - Removed from initial analysis flow
            # if self.qa_agent:
            #     logger.info(f"Running QA/Refinement for '{brand_name}' report...")
            #     final_report = self.qa_agent.review_and_summarize(report, evaluation_results)
            #     logger.info(f"QA/Refinement complete for '{brand_name}'.")
            # else:
            #      logger.warning("QA Agent not initialized, skipping refinement step.")
            #      final_report = report

            # Return the report generated by the ReporterAgent
            final_report = report

            logger.info(f"Analysis pipeline finished successfully for '{brand_name}'.")
            return final_report

        except Exception as e:
            logger.exception(f"An error occurred during the analysis pipeline for '{brand_name}': {e}")
            return {"error": f"Pipeline error for {brand_name}: {str(e)}"}

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # --- Load .env variables ---
    try:
        from dotenv import load_dotenv
        # Load environment variables from .env file in the project root
        # Assumes .env is in the same directory where you run the script (project root)
        # --- Correction: Load from specified path ---
        dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env') # Go up two levels from orchestrator.py
        # Alternative if running from project root:
        dotenv_path_alt = 'brand_navigator/.env'
        # Use the path relative to CWD since script is run from project root
        load_dotenv(dotenv_path=dotenv_path_alt, override=True)
        # ---------------------------------------------
        logger.info(f".env file loaded successfully from {dotenv_path_alt} (Override Mode).")
        # +++ Debugging +++
        loaded_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"Value of OPENAI_API_KEY after load_dotenv: {'Exists' if loaded_key else 'None'}")
        # +++++++++++++++++
    except ImportError:
        logger.warning("python-dotenv library not found. Skipping .env loading.")
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")
    # --------------------------

    orchestrator = OrchestratorAgent()
    test_brand = "InnovateNow" # Or try another name

    print(f"\n--- Running Analysis for '{test_brand}' (Markdown Output) ---")
    # Make sure OPENAI_API_KEY is set in environment (now loaded from .env)!
    markdown_report = orchestrator.run_analysis(test_brand, output_format='markdown')

    if isinstance(markdown_report, str):
        print(markdown_report)
    elif isinstance(markdown_report, dict) and 'error' in markdown_report:
        print(f"Analysis failed: {markdown_report['error']}")
    else:
        print(f"Analysis completed but returned unexpected type: {type(markdown_report)}")
        print(markdown_report)

    # Example for a different format (will show placeholder messages)
    # print(f"\n--- Running Analysis for '{test_brand}' (HTML Output) ---")
    # html_output = orchestrator.run_analysis(test_brand, output_format='html')
    # print(html_output)
