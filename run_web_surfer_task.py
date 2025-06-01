# run_web_surfer_task.py
import os
import sys
from autogen.agentchat.contrib.multimodal_web_surfer import MultiModalWebSurfer # Ensure this import path is correct for autogen 0.5.7

def main():
    task_string = os.environ.get("WEBSURFER_TASK")
    if not task_string:
        print("Error: WEBSURFER_TASK environment variable not set.", file=sys.stderr)
        sys.exit(1)

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Starting web surfer task: {task_string}", file=sys.stderr) # Log progress

    try:
        news_surfer = MultiModalWebSurfer(
            name="job_news_surfer",
            llm_config={
                "config_list": [
                    {
                        "model": os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo"),
                        "api_key": openai_api_key,
                    }
                ],
                "temperature": float(os.environ.get("LLM_TEMPERATURE", 0.0)),
            },
            browser_config={
                "browser_type": os.environ.get("PLAYWRIGHT_BROWSER_TYPE", "chromium"),
                "headless": os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
                "viewport_size": {"width": 1280, "height": 720},
            }
        )

        agent_response = news_surfer.chat(task_string)

        if agent_response:
            print(agent_response) # Output summary to stdout
        else:
            print("Error: Agent returned an empty response.", file=sys.stderr)
            sys.exit(1)

        print("Web surfer task completed successfully.", file=sys.stderr)

    except Exception as e:
        print(f"An error occurred during the web surfing task: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
