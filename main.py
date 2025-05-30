import os
from fastapi import FastAPI, HTTPException
from autogen.agentchat.contrib.multimodal_web_surfer import MultiModalWebSurfer

app = FastAPI()

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
                "ws_endpoint": "ws://localhost:3388",
            }
        )

        # Create a task for the web surfer
        task = "Summarize the top 3 latest news headlines from BBC News."

        # Get the news using the web surfer
        agent_response = news_surfer.chat(task)

        # Return the response as JSON
        # Assuming agent_response itself is serializable or a string
        return {"news_summary": agent_response}

    except ConnectionRefusedError:
        raise HTTPException(status_code=503, detail="Playwright server not available. Make sure it's running on ws://localhost:3388")
    except Exception as e:
        # Catch any other exceptions during the process
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
