# brand_navigator/agents/orchestrator.py

import logging
import os

# Import the agents we've created
from .market_research import MarketResearchAgent
from .reporter import ReporterAgent
from .evaluator import EvaluatorAgent
from .qa import QAAgent

# Configure Logging
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
        # Agents are initialized here but called sequentially by the route now
        self.market_researcher = MarketResearchAgent()
        self.reporter = ReporterAgent()
        self.evaluator = EvaluatorAgent()
        self.qa_agent = QAAgent() # Keep QA agent initialized here
        logger.info("OrchestratorAgent initialized with worker agents.")

    # The complex run_analysis logic is removed, as the route will call agents directly or via orchestrator attributes.
    # The main responsibility left here is holding the agent instances.

# Example Usage (Restore original test if needed, but recommend testing via Flask)
if __name__ == '__main__':
    print("OrchestratorAgent defined. Run Flask app for integrated testing.")
    # You might want to add simple tests here later to check agent initializations
