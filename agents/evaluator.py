import logging
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from openai import OpenAI, RateLimitError, APIError
    openai_available = True
except ImportError:
    openai_available = False
    logger.warning("OpenAI library not found. Please install it (`pip install openai`). EvaluatorAgent will not function.")
    OpenAI = None # Define OpenAI as None if import fails

class EvaluatorAgent:
    """
    Agent responsible for evaluating a brand name based on research data
    using an LLM (e.g., GPT-4o).
    """

    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the Evaluator Agent.

        Args:
            model (str): The OpenAI model to use for evaluation.
        """
        self.client = None
        self.model = None
        if not openai_available:
             logger.error("EvaluatorAgent cannot be initialized: OpenAI library is missing.")
             return
        try:
            # +++ Debugging +++
            key_check = os.getenv("OPENAI_API_KEY")
            logger.info(f"Checking for OPENAI_API_KEY inside EvaluatorAgent.__init__: {'Exists' if key_check else 'None'}")
            # +++++++++++++++++

            # --- Explicitly load API key ---
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                 logger.error("OPENAI_API_KEY not found in environment after attempting to load .env.")
                 # Raise an error or handle appropriately - preventing client initialization
                 raise ValueError("OPENAI_API_KEY environment variable not set.")

            # Pass the key explicitly
            self.client = OpenAI(api_key=api_key)
            # -------------------------------

            # Optional: Check if API key is valid by making a simple call
            # self.client.models.list()
            self.model = model
            logger.info(f"EvaluatorAgent initialized with model: {self.model}")
        except ValueError as ve:
             # Handle the specific case where API key wasn't found
             logger.error(f"Initialization failed: {ve}")
             self.client = None # Ensure client is None
        except Exception as e:
            logger.exception(f"Failed to initialize OpenAI client: {e}. Ensure OPENAI_API_KEY is set and valid.")
            self.client = None # Ensure client is None on failure


    def _construct_prompt(self, brand_name: str, research_data: dict) -> str:
        """Constructs the prompt for the LLM evaluation."""
        prompt = f"""
        **Brand Name Evaluation Request**

        **Brand Name:** {brand_name}

        **Market Research Summary:**
        Please evaluate the brand name '{brand_name}' based on the following market research data. Consider aspects like:
        1.  **Linguistic Qualities:** Is it easy to pronounce, spell, and remember? Does it sound appealing? Any potential negative connotations (globally or culturally)?
        2.  **Memorability & Distinctiveness:** How memorable and unique is the name itself? How does its distinctiveness compare considering the potential conflicts found in the research data?
        3.  **Relevance:** Does the name hint at the potential product/service category or target audience? Is it abstract or descriptive? (State assumptions if made).
        4.  **Availability Issues:** Briefly summarize the potential conflicts found in web search, social media, domains, and trademarks based *only* on the provided data. Assess the likely severity (e.g., high conflict if exact .com and social handles taken, low if only obscure mentions).
        5.  **Overall Potential Score:** Provide an overall potential score from 1 (very poor) to 10 (excellent), considering all factors, especially availability.

        **Research Data:**
        ```json
        {json.dumps(research_data, indent=2, default=str)}
        ```
        Note: 'potentially_available' domain status means it might be available but requires manual verification.
        Note: Trademark check via web search is basic; 'potential_conflict_found_on_site' requires deeper investigation.

        **Evaluation Output Format:**
        Provide your evaluation strictly in JSON format with the following keys ONLY:
        - "linguistic_analysis" (string: detailed analysis)
        - "memorability_distinctiveness" (string: analysis)
        - "relevance" (string: analysis, state assumptions if made)
        - "availability_summary" (string: summary of potential issues based on data and severity assessment)
        - "overall_score" (integer: 1-10)

        **JSON Evaluation Output:**
        """
        return prompt

    def evaluate(self, brand_name: str, research_data: dict) -> dict:
        """
        Evaluates the brand name using the configured LLM.

        Args:
            brand_name (str): The brand name to evaluate.
            research_data (dict): The consolidated data from MarketResearchAgent.

        Returns:
            dict: A dictionary containing the LLM's evaluation, structured as requested in the prompt,
                  or an error dictionary.
        """
        logger.info(f"Starting evaluation for brand name: '{brand_name}'")

        if not self.client:
             logger.error("OpenAI client not initialized. Cannot perform evaluation.")
             return {"error": "EvaluatorAgent not properly initialized (OpenAI client missing or invalid API key)."}

        if not research_data:
            logger.warning(f"No research data provided for evaluating '{brand_name}'. Cannot perform evaluation.")
            return {"error": "Missing research data for evaluation."}

        prompt = self._construct_prompt(brand_name, research_data)
        logger.debug(f"Constructed prompt for {brand_name}") # Avoid logging full prompt in production

        try:
            logger.info(f"Sending request to OpenAI model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant specialized in brand name evaluation. Provide analysis strictly in the requested JSON format."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4, # Lower temperature for more focused, less creative output
                response_format={ "type": "json_object" } # Request JSON output
            )

            llm_output_raw = response.choices[0].message.content
            logger.info(f"Received response from {self.model} for '{brand_name}'.")
            logger.debug(f"Raw LLM output: {llm_output_raw}")

            try:
                evaluation_result = json.loads(llm_output_raw)
                expected_keys = ["linguistic_analysis", "memorability_distinctiveness", "relevance", "availability_summary", "overall_score"]
                # Stricter validation: Ensure *only* expected keys exist
                if all(key in evaluation_result for key in expected_keys) and len(evaluation_result) == len(expected_keys):
                    logger.info(f"Successfully parsed evaluation for '{brand_name}'.")
                    # Ensure score is an integer
                    try:
                        evaluation_result['overall_score'] = int(evaluation_result['overall_score'])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not parse 'overall_score' as integer for {brand_name}. Value: {evaluation_result.get('overall_score')}")
                        # Decide how to handle: return error, set default, or leave as is? Returning error for now.
                        return {"error": "LLM response format error (invalid overall_score type).", "raw_response": llm_output_raw}

                    return evaluation_result
                else:
                    logger.error(f"LLM response for '{brand_name}' has incorrect keys. Expected: {expected_keys}, Got: {list(evaluation_result.keys())}. Raw: {llm_output_raw}")
                    return {"error": "LLM response format error (incorrect keys).", "raw_response": llm_output_raw}

            except json.JSONDecodeError as json_err:
                logger.error(f"Failed to parse JSON response from LLM for '{brand_name}': {json_err}. Raw: {llm_output_raw}")
                return {"error": "Failed to parse LLM JSON response.", "raw_response": llm_output_raw}

        except RateLimitError as rle:
            logger.error(f"OpenAI rate limit exceeded during evaluation for '{brand_name}': {rle}")
            return {"error": f"OpenAI rate limit exceeded: {rle}"}
        except APIError as apie:
            logger.error(f"OpenAI API error during evaluation for '{brand_name}': {apie}")
            # Handle specific API errors if needed (e.g., invalid request, auth error)
            return {"error": f"OpenAI API error: {apie}"}
        except Exception as e:
            logger.exception(f"An unexpected error occurred during evaluation for '{brand_name}': {e}")
            return {"error": f"An unexpected error occurred during evaluation: {str(e)}"}

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # Ensure OPENAI_API_KEY is set in your environment variables or .env file
    if not openai_available:
        print("OpenAI library not installed. Skipping EvaluatorAgent tests.")
    else:
        evaluator = EvaluatorAgent(model="gpt-4o")
        if not evaluator.client:
            print("OpenAI client failed to initialize. Please check your API key and network connection.")
        else:
            # Dummy data for InnovateNow (likely conflicts)
            dummy_research_innovatenow = {
              "brand_name": "InnovateNow",
              "web_search": {
                "web_links": [
                  {"url": "https://innovatenow.com", "title": "InnovateNow Official Website", "snippet": "..."},
                  {"url": "https://somecorp.com/innovatenow", "title": "About InnovateNow - Company Info", "snippet": "..."}
                ],
                "potential_conflicts": [
                  {"url": "https://innovatenow.com", "title": "InnovateNow Official Website", "reason": "Brand name found in title or domain"},
                  {"url": "https://somecorp.com/innovatenow", "title": "About InnovateNow - Company Info", "reason": "Brand name found in title or domain"}
                ],
                "query_used": "\"InnovateNow\" brand OR company OR official website",
                "error": None
              },
              "social_media_search": {
                "platform_results": {
                  "Twitter": "used_mentioned",
                  "Instagram": "potentially_available_low_presence",
                  "Facebook": "used_mentioned",
                  "LinkedIn (Company)": "potentially_available_low_presence",
                  "LinkedIn (General)": "potentially_available_low_presence"
                },
                "queries_used": [
                    {"platform": "Twitter", "query": "site:twitter.com \"InnovateNow\""},
                    {"platform": "Instagram", "query": "site:instagram.com \"InnovateNow\""}
                    # ... other platforms omitted for brevity ...
                ],
                "error": None
              },
              "trademark_check": {
                "status": "potential_conflict_found_on_site",
                "details": ["Found 1 result(s)...", "...", "Example Hit..."],
                "database_checked": "USPTO TESS (via web search)",
                "query_used": "site:tess2.uspto.gov \"InnovateNow\"",
                "error": None
              },
              "domain_availability": {
                "innovatenow.com": "taken",
                "innovatenow.co": "taken",
                "innovatenow.io": "taken",
                "innovatenow.ai": "potentially_available",
                "innovatenow.org": "taken",
                "innovatenow.net": "taken"
              },
              "error": None
            }

            print(f"--- Evaluating Brand: {dummy_research_innovatenow['brand_name']} ---")
            evaluation_results = evaluator.evaluate(dummy_research_innovatenow['brand_name'], dummy_research_innovatenow)
            print("\n--- Evaluation Results (InnovateNow) ---")
            print(json.dumps(evaluation_results, indent=2))

            # Dummy data for ZyxoSphere (fewer conflicts)
            dummy_research_zyxosphere = {
              "brand_name": "ZyxoSphere",
              "web_search": {
                  "web_links": [],
                  "potential_conflicts": [],
                  "query_used": "\"ZyxoSphere\" brand OR company OR official website",
                  "error": None
              },
              "social_media_search": {
                "platform_results": {
                    "Twitter": "potentially_available_low_presence",
                    "Instagram": "potentially_available_low_presence",
                    "Facebook": "potentially_available_low_presence",
                    "LinkedIn (Company)": "potentially_available_low_presence",
                    "LinkedIn (General)": "potentially_available_low_presence"
                },
                "queries_used": [
                    {"platform": "Twitter", "query": "site:twitter.com \"ZyxoSphere\""}
                    # ... other platforms omitted ...
                ],
                "error": None
              },
              "trademark_check": {
                "status": "no_exact_match_found_on_site",
                "details": ["No exact match...", "NOTE: ..."],
                "database_checked": "USPTO TESS (via web search)",
                "query_used": "site:tess2.uspto.gov \"ZyxoSphere\"",
                "error": None
              },
              "domain_availability": {
                "zyxosphere.com": "potentially_available",
                "zyxosphere.co": "potentially_available",
                "zyxosphere.io": "potentially_available",
                "zyxosphere.ai": "potentially_available",
                "zyxosphere.org": "potentially_available",
                "zyxosphere.net": "potentially_available"
              },
              "error": None
            }
            print(f"\n--- Evaluating Brand: {dummy_research_zyxosphere['brand_name']} ---")
            evaluation_results_2 = evaluator.evaluate(dummy_research_zyxosphere['brand_name'], dummy_research_zyxosphere)
            print("\n--- Evaluation Results (ZyxoSphere) ---")
            print(json.dumps(evaluation_results_2, indent=2))
