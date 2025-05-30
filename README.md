# News Summarizer API

This project is a FastAPI application that uses a multimodal web surfer (Autogen's `MultiModalWebSurfer`) to fetch and summarize the latest news headlines.

## Getting Started

### Prerequisites

*   **Python 3.7+**
*   **Running Playwright Server:**
    *   This application connects to an existing Playwright server. Ensure you have one running and accessible at `ws://localhost:3388`.
    *   You might need to install Playwright system dependencies and browsers first: `python -m playwright install`
    *   The Playwright server itself needs to be launched separately. The `connect_existing` option in the code implies that this application does not manage the server's lifecycle.
*   **LLM API Key and Configuration:**
    *   The application requires an LLM (e.g., OpenAI GPT model) to process and summarize the web content.
    *   You need to update the placeholder LLM configuration in `main.py` with your actual API key and desired model. Look for the `llm_config` dictionary within the `/news` endpoint. Specifically, set the `OPENAI_API_KEY` environment variable or replace `"your_api_key_here"` directly.

### Installation

1.  **Clone the repository** (if you are working with this project locally):
    ```bash
    # git clone <repository_url>
    # cd <repository_directory>
    ```
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

1.  Ensure your Playwright server is running on `ws://localhost:3388`.
2.  Ensure you have configured your LLM API key in `main.py` or via the `OPENAI_API_KEY` environment variable.
3.  Start the FastAPI application using Uvicorn:
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The application will be available at `http://localhost:8000`.

## Endpoint

### `/news`

*   **Method:** `GET`
*   **URL:** `/news`
*   **Description:** Fetches and summarizes the top 3 latest news headlines from a pre-configured news source (e.g., BBC News) using a multimodal web surfing agent.
*   **Success Response:**
    *   **Code:** `200 OK`
    *   **Content Example:**
        ```json
        {
            "news_summary": "AI has made groundbreaking advancements in climate change prediction, according to recent reports..."
        }
        ```
*   **Error Responses:**
    *   **Code:** `503 Service Unavailable`
        *   **Content Example (Playwright server unavailable):**
            ```json
            {
                "detail": "Playwright server not available. Make sure it's running on ws://localhost:3388"
            }
            ```
    *   **Code:** `500 Internal Server Error`
        *   **Content Example (Other processing error):**
            ```json
            {
                "detail": "An error occurred: Specific error message from the server."
            }
            ```

## Running Tests

To run the automated tests for this application:

1.  Ensure you have installed the development dependencies (which should be covered by `requirements.txt` if `pytest` is included, or `unittest` is standard).
2.  Navigate to the root directory of the project.
3.  Run the tests using `pytest` (recommended) or `unittest`:

    Using `pytest` (if you add `pytest` to `requirements.txt` and install it):
    ```bash
    pytest
    ```

    Or using `unittest`:
    ```bash
    python -m unittest discover tests
    ```
    This will discover and run all tests in the `tests` directory.
