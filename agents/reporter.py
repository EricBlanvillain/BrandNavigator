# brand_navigator/agents/reporter.py

import logging
import os
from datetime import datetime
# Depending on output format, might need:
# import markdown
# from jinja2 import Environment, FileSystemLoader # For HTML reports
# from weasyprint import HTML # For PDF from HTML

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReporterAgent:
    """
    Agent responsible for compiling research and evaluation findings into a structured report.
    """

    def __init__(self, template_dir: str = None):
        """
        Initialize the Reporter Agent.

        Args:
            template_dir (str, optional): Path to a directory containing report templates (e.g., for Jinja2). Defaults to None.
        """
        self.template_dir = template_dir
        # Example: Setup Jinja2 if using HTML templates
        # if self.template_dir:
        #     self.jinja_env = Environment(loader=FileSystemLoader(self.template_dir))
        logger.info("ReporterAgent initialized.")
        if template_dir:
            logger.info(f"Using template directory: {template_dir}")


    def _format_section(self, title: str, data: dict) -> str:
        """Helper method to format a section of the report (e.g., using Markdown)."""
        # Basic Markdown formatting example
        lines = [f"## {title}\n"]
        if isinstance(data, dict):
            for key, value in data.items():
                lines.append(f"- **{key.replace('_', ' ').title()}**: {value}")
        elif isinstance(data, list):
             for item in data:
                 lines.append(f"- {item}")
        else:
            lines.append(str(data))
        return "\n".join(lines) + "\n"


    def generate_report(self, brand_name: str, research_data: dict, evaluation_data: dict = None, output_format: str = 'markdown') -> str | bool:
        """
        Generates a report based on the provided data.

        Args:
            brand_name (str): The brand name being reported on.
            research_data (dict): Data from the MarketResearchAgent.
            evaluation_data (dict, optional): Data from the EvaluatorAgent. Defaults to None.
            output_format (str): The desired output format ('markdown', 'html', 'pdf'). Defaults to 'markdown'.

        Returns:
            str | bool: The generated report content as a string (for markdown/html)
                        or a boolean indicating success/failure (for file-based formats like PDF),
                        or None if an error occurs.
        """
        logger.info(f"Generating report for '{brand_name}' in {output_format} format.")

        if not research_data:
            logger.error("Cannot generate report without research data.")
            return None

        report_content = []
        report_title = f"Brand Analysis Report: {brand_name}"
        report_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- Report Generation Logic ---
        if output_format == 'markdown':
            report_content.append(f"# {report_title}")
            report_content.append(f"_Generated on: {report_date}_\n")

            # Market Research Section
            if research_data:
                 report_content.append(self._format_section("Market Research Summary", research_data.get('web_search', {})))
                 report_content.append(self._format_section("Social Media Presence", research_data.get('social_media_search', {})))
                 report_content.append(self._format_section("Trademark Check", research_data.get('trademark_check', {})))

            # *** Add Domain Availability Section ***
            if research_data.get('domain_availability'):
                report_content.append(self._format_section("Domain Availability", research_data['domain_availability']))
            # ******************************************

            # --- Evaluation Section ---
            report_content.append("\n## Brand Evaluation (via LLM)\n") # Add section header
            if evaluation_data:
                if evaluation_data.get("error"):
                     report_content.append(f"\n*Evaluation Error: {evaluation_data['error']}*")
                     # Optionally include raw response if available
                     if evaluation_data.get('raw_response'):
                         report_content.append(f"\n_Raw LLM Response (on error):_\n```\n{evaluation_data['raw_response']}\n```")
                else:
                    # Format the valid evaluation data
                    # Use title case for keys in the report
                    formatted_eval = {
                        key.replace('_', ' ').title(): value
                        for key, value in evaluation_data.items()
                    }
                    report_content.append(self._format_section("Evaluation Summary", formatted_eval))
            else:
                report_content.append("\n_(No evaluation data provided or evaluation skipped)_")
            # --------------------------

            # TODO: Add QA/Suggestions Section if applicable

            final_report = "\n".join(report_content)
            logger.info(f"Markdown report generated successfully for '{brand_name}'.")
            return final_report

        elif output_format == 'html':
            # TODO: Implement HTML report generation (possibly using Jinja2)
            logger.warning("HTML report generation is not yet implemented.")
            # Example using Jinja:
            # template = self.jinja_env.get_template('report_template.html')
            # html_content = template.render(title=report_title, date=report_date, ...)
            # return html_content
            return "<html><body><h1>HTML Report Not Implemented</h1></body></html>" # Placeholder

        elif output_format == 'pdf':
            # TODO: Implement PDF report generation (possibly HTML -> PDF)
            logger.warning("PDF report generation is not yet implemented.")
            # Example using WeasyPrint:
            # html_for_pdf = self.generate_report(brand_name, research_data, evaluation_data, output_format='html')
            # pdf_bytes = HTML(string=html_for_pdf).write_pdf()
            # with open(f"{brand_name}_report.pdf", "wb") as f:
            #     f.write(pdf_bytes)
            # return True # Indicate success
            return False # Indicate failure (not implemented)

        else:
            logger.error(f"Unsupported report format requested: {output_format}")
            return None
        # --- End Report Generation Logic ---


# Example Usage (for testing purposes)
if __name__ == '__main__':
    reporter = ReporterAgent()
    # Dummy data simulating output from other agents
    dummy_research = {
        'brand_name': 'ExampleBrandName',
        'web_search': {'web_links': ['example.com'], 'potential_conflicts': [], 'domain_availability': {'examplebrandname.com': 'taken'}},
        'social_media_search': {'platform_results': {'twitter': 'handle_taken', 'instagram': 'handle_available'}},
        'trademark_check': {'status': 'potential_conflict', 'details': ['Similar mark found in class X'], 'database_checked': 'US'}
    }
    dummy_evaluation = {
        'linguistic_score': 8.5,
        'sentiment_analysis': 'positive',
        'memorability': 'high'
    }

    print("--- Generating Markdown Report ---")
    markdown_report = reporter.generate_report("ExampleBrandName", dummy_research, dummy_evaluation, output_format='markdown')
    if markdown_report:
        print(markdown_report)

    print("\n--- Generating HTML Report (Placeholder) ---")
    html_report = reporter.generate_report("ExampleBrandName", dummy_research, output_format='html')
    print(html_report)

    print("\n--- Generating PDF Report (Placeholder) ---")
    pdf_success = reporter.generate_report("ExampleBrandName", dummy_research, output_format='pdf')
    print(f"PDF generation status: {pdf_success}")
