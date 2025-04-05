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
    logger.warning("OpenAI library not found. Please install it (`pip install openai`). QAAgent will not function.")
    OpenAI = None # Define OpenAI as None if import fails


class QAAgent:
    """
    Agent responsible for answering follow-up questions about a brand analysis report,
    using the original report data as context.
    """

    def __init__(self, model: str = "gpt-4o"): # Use the same model as evaluator for consistency
        """
        Initialize the QA Agent.
        """
        self.client = None
        self.model = None
        if not openai_available:
             logger.error("QAAgent cannot be initialized: OpenAI library is missing.")
             return
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set for QAAgent.")
            self.client = OpenAI(api_key=api_key)
            self.model = model
            logger.info(f"QAAgent initialized with model: {self.model}")
        except ValueError as ve:
             logger.error(f"QAAgent initialization failed: {ve}")
        except Exception as e:
            logger.exception(f"Failed to initialize OpenAI client for QAAgent: {e}")

    def _construct_qa_prompt(self, question: str, research_data: dict, evaluation_data: dict) -> str:
        """Constructs the prompt for the LLM to answer a follow-up question."""

        # Combine context concisely
        context = {
            "brand_name": research_data.get('brand_name', 'N/A'),
            "research_summary": {
                "web_conflict_count": len(research_data.get('web_search', {}).get('potential_conflicts', [])),
                "social_media_status": research_data.get('social_media_search', {}).get('platform_results', {}),
                "domain_status": research_data.get('domain_availability', {}),
                "trademark_status": research_data.get('trademark_check', {}).get('status', 'unknown')
            },
            "evaluation_summary": evaluation_data if evaluation_data and not evaluation_data.get('error') else "Evaluation not available or failed."
        }

        prompt = f"""
        **Context:**
        You are assisting a user who received an initial analysis for the brand name '{context['brand_name']}'.
        The key findings from the analysis are summarized below:
        ```json
        {json.dumps(context, indent=2, default=str)}
        ```

        **User's Follow-up Question:**
        {question}

        **Task:**
        Answer the user's question.
        - If the question asks for information *directly present* in the provided context data (e.g., "What was the .com domain status?"), answer based *only* on that context.
        - If the question asks for *creative brainstorming* or *suggestions* related to the analyzed brand (e.g., "Suggest alternative names", "What are some tagline ideas?"), use the context as background inspiration and provide a few relevant ideas.
        - If the context doesn't contain the information to answer a factual question, clearly state that the information isn't available in the report data.
        - Do not perform new searches or access external information.
        - Keep your answer concise and helpful.

        **Answer:**
        """
        return prompt

    def answer_followup(self, question: str, research_data: dict, evaluation_data: dict) -> dict:
        """
        Answers a user's follow-up question based on the provided analysis context.

        Args:
            question (str): The user's follow-up question.
            research_data (dict): The original market research data.
            evaluation_data (dict): The original evaluation data.

        Returns:
            dict: A dictionary containing the answer under the key 'answer' or an 'error'.
        """
        logger.info(f"QA Agent received follow-up question: '{question}'")

        if not self.client:
             logger.error("QAAgent OpenAI client not initialized. Cannot answer question.")
             return {"error": "QA Agent is not properly initialized."}

        if not research_data:
            logger.warning("Missing context data for answering follow-up question.")
            return {"error": "Missing original analysis context to answer question."}

        # Construct the prompt using the question and context
        prompt = self._construct_qa_prompt(question, research_data, evaluation_data)
        logger.debug(f"Constructed QA prompt for question: '{question}'")

        try:
            logger.info(f"Sending QA request to OpenAI model: {self.model}")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    # System prompt sets the role and constraints
                    {"role": "system", "content": "You are a helpful AI assistant answering follow-up questions about a brand analysis report based only on the provided context. Be concise."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3, # Low temperature for factual answers based on context
                max_tokens=150 # Limit response length
            )

            answer = response.choices[0].message.content.strip()
            logger.info(f"Received QA answer from {self.model}.")
            return {"answer": answer}

        except RateLimitError as rle:
            logger.error(f"OpenAI rate limit exceeded during QA: {rle}")
            return {"error": f"OpenAI rate limit exceeded: {rle}"}
        except APIError as apie:
            logger.error(f"OpenAI API error during QA: {apie}")
            return {"error": f"OpenAI API error: {apie}"}
        except Exception as e:
            logger.exception(f"An unexpected error occurred during QA: {e}")
            return {"error": f"An unexpected error occurred during QA: {str(e)}"}

# Remove old __main__ block - testing requires context
# if __name__ == '__main__':
#    ... (old example usage removed)
