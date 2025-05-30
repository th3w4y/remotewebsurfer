from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest

# Ensure the app can be imported. If main.py is in the root, this should work.
# If your project structure is different, you might need to adjust the Python path.
try:
    from main import app
except ImportError:
    import sys
    import os
    # Add the parent directory to the sys.path to find the main module
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from main import app


client = TestClient(app)

@patch('main.MultiModalWebSurfer')
def test_get_news_success(MockMultiModalWebSurfer):
    """
    Test the /news endpoint for a successful response.
    """
    # Configure the mock MultiModalWebSurfer
    mock_surfer_instance = MockMultiModalWebSurfer.return_value
    mock_surfer_instance.chat.return_value = "Breaking News: AI solves world hunger!"

    # Make a GET request to /news
    response = client.get("/news")

    # Assert that the response status code is 200
    assert response.status_code == 200

    # Assert that the response JSON contains the expected news summary
    assert response.json() == {"news_summary": "Breaking News: AI solves world hunger!"}
    MockMultiModalWebSurfer.assert_called_once()
    mock_surfer_instance.chat.assert_called_once_with("Summarize the top 3 latest news headlines from BBC News.")

@patch('main.MultiModalWebSurfer')
def test_get_news_playwright_unavailable(MockMultiModalWebSurfer):
    """
    Test the /news endpoint when the Playwright server is unavailable.
    """
    # Configure the mock MultiModalWebSurfer's __init__ to raise ConnectionRefusedError
    # This simulates the "connect_existing" browser_type failing.
    MockMultiModalWebSurfer.side_effect = ConnectionRefusedError("Simulated Playwright connection failed")

    # Make a GET request to /news
    response = client.get("/news")

    # Assert that the response status code is 503 (Service Unavailable)
    assert response.status_code == 503

    # Assert that the response JSON contains an appropriate error message
    assert response.json() == {"detail": "Playwright server not available. Make sure it's running on ws://localhost:3388"}
    MockMultiModalWebSurfer.assert_called_once()


@patch('main.MultiModalWebSurfer')
def test_get_news_generic_exception(MockMultiModalWebSurfer):
    """
    Test the /news endpoint for a generic exception during web surfing.
    """
    # Configure the mock MultiModalWebSurfer's chat method to raise a generic Exception
    mock_surfer_instance = MockMultiModalWebSurfer.return_value
    mock_surfer_instance.chat.side_effect = Exception("Simulated generic error during news retrieval")

    # Make a GET request to /news
    response = client.get("/news")

    # Assert that the response status code is 500 (Internal Server Error)
    assert response.status_code == 500

    # Assert that the response JSON contains an appropriate error message
    assert response.json() == {"detail": "An error occurred: Simulated generic error during news retrieval"}
    MockMultiModalWebSurfer.assert_called_once()
    mock_surfer_instance.chat.assert_called_once_with("Summarize the top 3 latest news headlines from BBC News.")
