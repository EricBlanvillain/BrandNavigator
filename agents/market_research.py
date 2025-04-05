import logging
import os
import time # Import time for potential delays/rate limiting
import requests # Add requests import

# Configure logging FIRST
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import whois
except ImportError:
    whois = None # Handle case where library is not installed
    # Now logger is defined, so this will work:
    logger.error("`python-whois` library not found. Please install it (`pip install python-whois`). Domain checks will be skipped.")
# We might need libraries for web requests, web scraping, or specific APIs
# import requests
# from bs4 import BeautifulSoup
# from some_trademark_api import TrademarkClient
# from some_social_media_api import SocialMediaClient
# from mcp_tool_imports import brave_web_search # Hypothetical import for the tool

class MarketResearchAgent:
    """
    Agent responsible for researching brand name usage across various platforms.
    """

    def __init__(self):
        """
        Initialize the Market Research Agent.
        Load Brave API Key.
        """
        logger.info("Initializing MarketResearchAgent...")
        self.brave_api_key = os.getenv('BRAVE_API_KEY')
        if not self.brave_api_key:
            logger.error("BRAVE_API_KEY not found in environment variables. Live web/social/trademark searches will fail.")
        self.brave_api_base_url = "https://api.search.brave.com/res/v1/web/search" # Use Web Search endpoint
        logger.info("MarketResearchAgent initialized.")

    def _make_brave_request(self, query: str, count: int = 10) -> dict:
        """ Helper function to make requests to the Brave Search API."""
        if not self.brave_api_key:
            return {"error": "Brave API Key is missing."}

        headers = {
            "X-Subscription-Token": self.brave_api_key, # Correct header name
            "Accept": "application/json"
        }
        params = {
            "q": query,
            "count": count
        }
        try:
            response = requests.get(self.brave_api_base_url, headers=headers, params=params, timeout=15) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            # Check if response is JSON before parsing
            if 'application/json' in response.headers.get('Content-Type', ''):
                 # Directly return the parsed JSON from Brave API
                 # Brave API structure includes {"web": {"results": [...]}}
                 return response.json()
            else:
                logger.error(f"Brave API returned non-JSON response for query '{query}'. Status: {response.status_code}, Content: {response.text[:200]}")
                return {"error": f"Brave API returned non-JSON content (Status: {response.status_code})"}

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout occurred while calling Brave API for query '{query}': {e}")
            return {"error": f"Timeout calling Brave API: {e}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Brave API for query '{query}': {e}")
            status_code = e.response.status_code if e.response else 'N/A'
            error_text = e.response.text[:200] if e.response else 'No response body'
            return {"error": f"Brave API request failed (Status: {status_code}): {e}. Details: {error_text}"}
        except Exception as e:
             logger.exception(f"Unexpected error during Brave API call for query '{query}': {e}")
             return {"error": f"Unexpected error calling Brave API: {str(e)}"}

    def search_web(self, brand_name: str) -> dict:
        """
        Searches the general web for occurrences of the brand name using Brave Search API.
        Args: brand_name
        Returns: dict summarizing findings.
        """
        logger.info(f"Starting web search for: {brand_name}")
        results = {
            'web_links': [],
            'potential_conflicts': [],
            'query_used': None,
            'error': None
        }
        query = f'"{brand_name}" brand OR company OR official website'
        results['query_used'] = query

        # Make the API call using the helper
        search_api_results = self._make_brave_request(query=query, count=10)

        # Check for errors from the API call itself
        if isinstance(search_api_results, dict) and search_api_results.get('error'):
            results['error'] = search_api_results['error']
            logger.error(f"Web search failed for {brand_name}: {results['error']}")
            return results

        # Process the successful results (assuming standard Brave structure)
        try:
            if isinstance(search_api_results, dict) and search_api_results.get('web') and isinstance(search_api_results['web'].get('results'), list):
                processed_urls = set()
                api_results_list = search_api_results['web']['results']
                logger.info(f"Processing {len(api_results_list)} web results from API.")

                for item in api_results_list:
                    link = item.get('url')
                    title = item.get('title')
                    snippet = item.get('description') # Brave uses 'description'

                    if link and link not in processed_urls:
                        processed_urls.add(link)
                        results['web_links'].append({'url': link, 'title': title, 'snippet': snippet})

                        # Simplified conflict check (as before)
                        try:
                            title_lower = str(title).lower() if title else ""
                            domain = ""
                            if link:
                                parts = link.split('/')
                                if len(parts) > 2:
                                    domain = parts[2].replace('www.', '')
                            domain_lower = domain.lower()
                        except Exception as parse_err:
                             logger.warning(f"Error parsing title/domain for URL {link}: {parse_err}")
                             title_lower = ""
                             domain_lower = ""

                        brand_lower = brand_name.lower()
                        if (brand_lower in title_lower) or (brand_lower in domain_lower):
                            results['potential_conflicts'].append({
                                'url': link,
                                'title': title,
                                'reason': 'Brand name found in title or domain'
                            })
            else:
                logger.warning(f"No results or unexpected format in Brave API response for {brand_name}. Data: {search_api_results}")
                # Not necessarily an error if Brave found nothing, but could be format issue
                if not results['web_links']:
                     logger.info(f"Brave API returned no web results for query: {query}")

        except Exception as e:
            logger.exception(f"Error processing Brave web search results for '{brand_name}': {e}")
            results['error'] = f"An exception occurred during web search result processing: {str(e)}"

        return results

    def search_social_media(self, brand_name: str) -> dict:
        """
        Searches social media platforms using targeted Brave web search.
        """
        logger.info(f"Starting social media presence check for: {brand_name}")
        results = {
            'platform_results': {},
            'queries_used': [],
            'error': None
        }
        platforms_to_check = {
            'Twitter': f'site:twitter.com "{brand_name}"',
            'Instagram': f'site:instagram.com "{brand_name}"',
            'Facebook': f'site:facebook.com "{brand_name}"',
            'LinkedIn (Company)': f'site:linkedin.com/company/ "{brand_name}"',
            'LinkedIn (General)': f'site:linkedin.com "{brand_name}" -site:linkedin.com/company/'
        }
        overall_error = None

        for platform, query in platforms_to_check.items():
            logger.info(f"Checking {platform} with query: {query}")
            results['queries_used'].append({'platform': platform, 'query': query})
            platform_status = "potentially_available_low_presence"
            error_msg = None

            # --- Add delay to avoid rate limiting ---
            time.sleep(0.8) # Pause for 0.8 seconds before the next API call
            # ----------------------------------------

            # Make the API call
            search_api_results = self._make_brave_request(query=query, count=3)

            # Check for API call errors
            if isinstance(search_api_results, dict) and search_api_results.get('error'):
                error_msg = f"API Error for {platform}: {search_api_results['error']}"
                logger.error(error_msg)
                platform_status = "check_error"
                overall_error = overall_error or error_msg # Store first error
            else:
                # Process successful results
                try:
                    brand_lower = brand_name.lower()
                    found_mention = False
                    if isinstance(search_api_results, dict) and search_api_results.get('web') and search_api_results['web'].get('results'):
                        for item in search_api_results['web']['results']:
                            item_title = item.get('title', '').lower()
                            item_url = item.get('url', '').lower()
                            if brand_lower in item_title or f"/{brand_lower}" in item_url:
                                platform_status = "used_mentioned"
                                found_mention = True
                                logger.info(f"Found potential usage/mention for '{brand_name}' on {platform}: {item.get('url')}")
                                break
                    if not found_mention:
                        logger.info(f"No direct profile/strong mentions found for '{brand_name}' on {platform} in top results.")
                except Exception as e:
                    error_msg = f"Exception processing results for {platform}: {str(e)}"
                    logger.error(error_msg)
                    platform_status = "check_error"
                    overall_error = overall_error or error_msg

            results['platform_results'][platform] = platform_status

        results['error'] = overall_error # Set overall error if any platform failed
        logger.info(f"Completed social media presence check for: {brand_name}")
        return results

    def check_trademarks(self, brand_name: str, country_code: str = 'US') -> dict:
        """
        Performs a basic trademark check using Brave web search.
        """
        logger.info(f"Starting basic trademark check for: {brand_name} in country: {country_code}")
        results = {
            'status': 'check_error',
            'details': [],
            'database_checked': f'{country_code} (Unsupported)',
            'query_used': None,
            'error': None
        }
        target_site = None
        if country_code == 'US':
            target_site = "tess2.uspto.gov"
            results['database_checked'] = 'USPTO TESS (via web search)'
        # TODO: Add other countries

        if not target_site:
            results['status'] = 'unsupported_country'
            results['error'] = f"Country code '{country_code}' not supported."
            return results

        query = f'site:{target_site} "{brand_name}"'
        results['query_used'] = query
        logger.info(f"Using trademark check query: {query}")

        # --- Add delay to avoid rate limiting ---
        time.sleep(0.8) # Pause for 0.8 seconds before the API call
        # ----------------------------------------

        # Make API Call
        search_api_results = self._make_brave_request(query=query, count=2)

        # Check API errors
        if isinstance(search_api_results, dict) and search_api_results.get('error'):
            results['error'] = f"API Error: {search_api_results['error']}"
            results['status'] = 'check_error'
            results['details'] = [f"Failed to query {target_site} via API."]
            logger.error(results['error'])
            return results

        # Process results
        try:
            found_hits = []
            if isinstance(search_api_results, dict) and search_api_results.get('web') and search_api_results['web'].get('results'):
                 found_hits = search_api_results['web']['results']
                 logger.info(f"Found {len(found_hits)} potential exact match(es) for '{brand_name}' on {target_site}.")
            else:
                 logger.info(f"No direct results found for '{brand_name}' on {target_site} via web search.")

            if found_hits:
                 results['status'] = 'potential_conflict_found_on_site'
                 results['details'] = [
                     f"Found {len(found_hits)} result(s) potentially related...",
                     "Further investigation required.",
                     f"Example Hit: {found_hits[0].get('title')} ({found_hits[0].get('url')})"
                 ]
            else:
                 results['status'] = 'no_exact_match_found_on_site'
                 results['details'] = [
                     f"No exact match for '{brand_name}' found via web search...",
                     "NOTE: This does NOT confirm availability..."
                 ]
            results['error'] = None # Clear error on success

        except Exception as e:
            logger.exception(f"Error processing trademark search results for '{brand_name}': {e}")
            results['status'] = 'check_error'
            results['details'] = [f"Exception processing results: {str(e)}"]
            results['error'] = f"Exception processing results: {str(e)}"

        logger.info(f"Completed basic trademark check processing for: {brand_name}. Status: {results['status']}")
        return results

    def check_domain_availability(self, brand_name: str, tlds: list[str] = None) -> dict:
        """
        Checks the availability of domain names based on the brand name for common TLDs.

        Args:
            brand_name (str): The base brand name (without TLD).
            tlds (list[str], optional): A list of TLDs to check (e.g., ['.com', '.co', '.io']).
                                        Defaults to a standard list if None.

        Returns:
            dict: A dictionary mapping domain names to their status ('available', 'taken', 'check_error', 'skipped').
        """
        if tlds is None:
            tlds = ['.com', '.co', '.io', '.ai', '.org', '.net'] # Default TLDs

        # Basic sanitization of brand name for domain use (remove spaces, special chars)
        base_domain = "".join(c for c in brand_name if c.isalnum()).lower()
        if not base_domain:
            logger.error(f"Could not generate a valid base domain from brand name: {brand_name}")
            return {"error": "Invalid base domain generated", "results": {}}

        logger.info(f"Starting domain availability check for base: {base_domain}, TLDs: {tlds}")
        domain_statuses = {}
        overall_error = None

        if whois is None:
             logger.warning("Skipping domain checks because python-whois library is not installed.")
             overall_error = "Skipped (python-whois library missing)"
             for tld in tlds:
                 domain_name = base_domain + tld
                 domain_statuses[domain_name] = 'skipped (library missing)'
             return {"error": overall_error, "results": domain_statuses}

        for tld in tlds:
            domain_name = base_domain + tld
            status = 'check_error'
            try:
                time.sleep(0.5)
                logger.debug(f"Checking WHOIS for: {domain_name}")
                w = whois.whois(domain_name)

                if w and w.creation_date:
                    logger.info(f"Domain {domain_name} appears to be TAKEN (Creation date: {w.creation_date}).")
                    status = 'taken'
                else:
                    logger.info(f"Domain {domain_name} appears to be AVAILABLE (or WHOIS query inconclusive).")
                    status = 'potentially_available'

            except whois.parser.PywhoisError as e:
                 logger.info(f"Domain {domain_name} likely AVAILABLE (PywhoisError: {e}).")
                 status = 'potentially_available'
            except ConnectionError as e:
                 logger.error(f"Connection error checking domain {domain_name}: {e}")
                 status = 'check_error (connection)'
                 overall_error = overall_error or "Connection error during domain check"
            except Exception as e:
                logger.error(f"Error checking domain {domain_name}: {type(e).__name__} - {e}")
                status = 'check_error'
                overall_error = overall_error or "Exception during domain check"

            domain_statuses[domain_name] = status

        logger.info("Completed domain availability check.")
        # Return a dict containing results and any overall error message
        return {"error": overall_error, "results": domain_statuses}

    def research(self, brand_name: str) -> dict:
        """
        Conducts comprehensive market research for a given brand name.
        """
        logger.info(f"Starting comprehensive research for: {brand_name}")
        if not brand_name or not isinstance(brand_name, str):
             logger.error("Invalid brand name provided for research.")
             return {"error": "Invalid brand name provided."}

        # Run individual checks using the updated methods
        web_results = self.search_web(brand_name)
        social_media_results = self.search_social_media(brand_name)
        trademark_results = self.check_trademarks(brand_name)
        domain_results_dict = self.check_domain_availability(brand_name)

        # Consolidate results
        consolidated_results = {
            'brand_name': brand_name,
            'web_search': web_results,
            'social_media_search': social_media_results,
            'trademark_check': trademark_results,
            'domain_availability': domain_results_dict.get('results', {}),
            # Consolidate errors from all steps
            'error': web_results.get('error') or social_media_results.get('error') or trademark_results.get('error') or domain_results_dict.get('error')
        }
        logger.info(f"Completed research for: {brand_name}")
        return consolidated_results

# Example Usage (for testing purposes)
if __name__ == '__main__':
    # This example usage will need to be updated for the new request/process flow
    # researcher = MarketResearchAgent()
    # test_name = "ExampleBrandName"
    # research_data = researcher.research(test_name)
    # import json
    # print(json.dumps(research_data, indent=2))
    print("MarketResearchAgent defined. Run orchestrator for testing.")
