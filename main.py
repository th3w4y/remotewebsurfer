import os
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_executor
from autogen.agentchat.contrib.multimodal_web_surfer import MultiModalWebSurfer

app = FastAPI()

PLAYWRIGHT_WS_ENDPOINT = os.environ.get("PLAYWRIGHT_WS_ENDPOINT", "ws://localhost:3388")

@app.get("/news")
async def get_news():
    try:
        # Initialize MultiModalWebSurfer
        news_surfer = MultiModalWebSurfer(
            name="news_surfer",
            # TODO: Replace with your actual LLM configuration
            llm_config={
                "config_list": [
                    {
                        "model": "gpt-3.5-turbo",
                        "api_key": os.environ.get("OPENAI_API_KEY", "your_api_key_here"),
                    }
                ],
                "temperature": 0,
            },
            browser_config={
                "browser_type": "connect_existing",
                "viewport_size": {"width": 1280, "height": 720},
                "ws_endpoint": PLAYWRIGHT_WS_ENDPOINT,
            }
        )

        # Create a task for the web surfer
        task = "Summarize the top 3 latest news headlines from BBC News."

        # Get the news using the web surfer
        agent_response = await run_in_executor(None, news_surfer.chat, task)

        # Return the response as JSON
        # Assuming agent_response itself is serializable or a string
        return {"news_summary": agent_response}

    except ConnectionRefusedError:
        raise HTTPException(status_code=503, detail=f"Playwright server not available. Make sure it's running on {PLAYWRIGHT_WS_ENDPOINT}")
    except Exception as e:
        # Catch any other exceptions during the process
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
