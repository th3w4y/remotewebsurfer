from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import pytest
import importlib

# Ensure the app can be imported. If main.py is in the root, this should work.
# If your project structure is different, you might need to adjust the Python path.
try:
    import main as main_module
except ImportError:
    import sys
    import os
    # Add the parent directory to the sys.path to find the main module
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import main as main_module


# client will be initialized within each test function that needs it,
# especially those involving module reloading.

@patch('main.MultiModalWebSurfer')
def test_get_news_success(MockMultiModalWebSurfer):
    client = TestClient(main_module.app)
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
def test_get_news_playwright_unavailable(MockMultiModalWebSurfer, monkeypatch):
    """
    Test the /news endpoint when the Playwright server is unavailable and custom endpoint is used.
    """
    custom_url = "ws://customhosterr:1234"
    monkeypatch.setenv("PLAYWRIGHT_WS_ENDPOINT", custom_url)
    importlib.reload(main_module)
    client = TestClient(main_module.app)

    MockMultiModalWebSurfer.side_effect = ConnectionRefusedError("Simulated connection failure")

    response = client.get("/news")
    assert response.status_code == 503
    expected_detail = f"Playwright server not available. Make sure it's running on {custom_url}"
    assert response.json() == {"detail": expected_detail}
    MockMultiModalWebSurfer.assert_called_once()


@patch('main.MultiModalWebSurfer')
def test_get_news_generic_exception(MockMultiModalWebSurfer):
    client = TestClient(main_module.app)
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

@patch('main.MultiModalWebSurfer')
def test_get_news_success_with_custom_playwright_endpoint(MockMultiModalWebSurfer, monkeypatch):
    """
    Test the /news endpoint for a successful response with a custom Playwright WebSocket endpoint.
    """
    custom_endpoint = "ws://anothercustom.host:5678"
    monkeypatch.setenv("PLAYWRIGHT_WS_ENDPOINT", custom_endpoint)
    importlib.reload(main_module)
    client = TestClient(main_module.app)

    mock_surfer_instance = MockMultiModalWebSurfer.return_value
    mock_surfer_instance.chat.return_value = "News from custom endpoint!"

    response = client.get("/news")
    assert response.status_code == 200
    assert response.json() == {"news_summary": "News from custom endpoint!"}

    # Check if MultiModalWebSurfer was initialized with the custom ws_endpoint
    called_args, called_kwargs = MockMultiModalWebSurfer.call_args
    assert "browser_config" in called_kwargs
    expected_browser_config = {
        "browser_type": "connect_existing",
        "viewport_size": {"width": 1280, "height": 720},
        "ws_endpoint": custom_endpoint
    }
    assert called_kwargs["browser_config"] == expected_browser_config
    MockMultiModalWebSurfer.assert_called_once()
    mock_surfer_instance.chat.assert_called_once_with("Summarize the top 3 latest news headlines from BBC News.")
