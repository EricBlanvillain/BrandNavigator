import json
import pytest
from flask import session

# --- Test Home Page --- #

def test_home_page(client):
    """Test that the home page loads correctly."""
    response = client.get('/')
    assert response.status_code == 200
    assert b"BrandNavigator AI" in response.data # Check for a keyword in the HTML

# --- Test /analyze Endpoint --- #

def test_analyze_success(client, mocker):
    """Test successful analysis, mocking the orchestrator agents."""
    # Mock the results from the agents
    mock_research = {"domain_available": True, "social_available": False, "web_mentions": 5}
    mock_evaluation = {"score": 85, "pros": ["Unique"], "cons": ["Hard to spell"]}
    mock_report = "# Analysis Report\n\n## Research\nDomain Available: Yes\n\n## Evaluation\nScore: 85" # Example markdown

    # Use mocker to replace methods on the orchestrator instance used by the app
    # NOTE: Adjust the path 'brand_navigator.app.orchestrator' if it's imported differently
    mocker.patch('app.orchestrator.market_researcher.research', return_value=mock_research)
    mocker.patch('app.orchestrator.evaluator.evaluate', return_value=mock_evaluation)
    mocker.patch('app.orchestrator.reporter.generate_report', return_value=mock_report)

    response = client.post('/analyze', data={'brand_name': 'TestBrand'})

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['brand_name'] == 'TestBrand'
    assert data['research_data'] == mock_research
    assert data['evaluation_data'] == mock_evaluation
    assert data['report_markdown'] == mock_report

    # Check if data was stored in session (requires request context)
    with client.session_transaction() as sess:
        assert sess.get('analyzed_brand') == 'TestBrand'
        assert sess.get('research_data') == mock_research
        assert sess.get('evaluation_data') == mock_evaluation

def test_analyze_missing_brand(client):
    """Test analysis request with no brand name provided."""
    response = client.post('/analyze', data={'brand_name': ''})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert data['error'] == 'Missing Input'

# --- Test /qa Endpoint --- #

def test_qa_success(client, mocker):
    """Test successful QA request after an analysis."""
    mock_qa_answer = "The domain was available according to the research."
    mock_research_context = {"domain_available": True}
    mock_eval_context = {"score": 85}

    # Mock the QA agent's answer_followup method
    # NOTE: Adjust path 'brand_navigator.app.qa_agent' if imported differently
    mocker.patch('app.qa_agent.answer_followup', return_value={'answer': mock_qa_answer})

    # Manually set session data to simulate prior analysis
    with client.session_transaction() as sess:
        sess['research_data'] = mock_research_context
        sess['evaluation_data'] = mock_eval_context
        sess['analyzed_brand'] = 'PreviousBrand'

    response = client.post('/qa', data={'question': 'Was the domain available?'})

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['success'] is True
    assert data['answer'] == mock_qa_answer

def test_qa_missing_context(client):
    """Test QA request when no analysis has been run (no session data)."""
    # Ensure session is empty before this test if tests share context
    with client.session_transaction() as sess:
        sess.clear()

    response = client.post('/qa', data={'question': 'Any question?'})

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert data['error'] == 'Missing Context'

def test_qa_missing_question(client):
    """Test QA request with no question provided."""
    # Need context for this check to pass
    with client.session_transaction() as sess:
        sess['research_data'] = {"some": "data"}

    response = client.post('/qa', data={'question': ''})

    assert response.status_code == 400
    data = json.loads(response.data)
    assert data['success'] is False
    assert data['error'] == 'Missing Input'

# Add more tests here for:
# - Cases where agents return errors
# - Cases where agents are not initialized
# - Edge cases for input data
