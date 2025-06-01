import os
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from kubernetes import client, config
from kubernetes.client.rest import ApiException

# Initialize FastAPI app
app = FastAPI()

# Kubernetes client initialization
try:
    config.load_incluster_config()  # For running inside a K8s cluster
except config.ConfigException:
    try:
        config.load_kube_config()  # For local development/testing
    except config.ConfigException:
        raise RuntimeError("Could not load Kubernetes configuration. Ensure you are running in a cluster or have a valid kubeconfig.")

batch_v1 = client.BatchV1Api()
core_v1 = client.CoreV1Api()

# In-memory storage for task to job mapping (replace with a persistent store in a real application)
task_to_job_map = {}

# --- Pydantic Models ---
class NewsTaskRequest(BaseModel):
    query: str

class NewsTaskResponse(BaseModel):
    task_id: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    job_name: str | None = None
    message: str | None = None

class NewsResultResponse(BaseModel):
    task_id: str
    summary: str | None = None
    error: str | None = None

# --- Helper Functions ---
def get_job_status_string(job_status_obj: client.V1JobStatus) -> str:
    if job_status_obj.succeeded and job_status_obj.succeeded > 0:
        return "Succeeded"
    elif job_status_obj.failed and job_status_obj.failed > 0:
        return "Failed"
    elif job_status_obj.active and job_status_obj.active > 0:
        return "Running"
    # Consider 'conditions' for more granular pending/progressing states if needed
    # For simplicity, anything not active, succeeded, or failed is "Pending" or "Unknown"
    # Check for specific conditions like 'Suspended' if that's a possible state.
    # A job might not have 'active' if it's still scheduling or has completed.
    # If no other conditions, assume it's pending or in an unknown state.
    # The conditions array might give more details, e.g., type: "Pending"
    if job_status_obj.conditions:
        for condition in job_status_obj.conditions:
            if condition.type == "Failed" and condition.status == "True":
                return "Failed" # Ensure failed condition is caught
            if condition.type == "Complete" and condition.status == "True": # K8s uses "Complete" for Succeeded
                return "Succeeded"
    return "Pending/Unknown"


# --- API Endpoints ---
@app.post("/news_task", response_model=NewsTaskResponse, status_code=202)
async def submit_news_task(task_request: NewsTaskRequest):
    task_id = str(uuid.uuid4())
    # Ensure job_name is DNS-compliant (lowercase, numbers, hyphens)
    job_name = f"news-surfer-job-{task_id[:8]}" # Shortened UUID for job name part

    # Define the Kubernetes Job
    container = client.V1Container(
        name="news-surfer-runner",
        image="your-container-registry/news-job-runner:latest", # Replace with your actual image
        env=[
            client.V1EnvVar(name="WEBSURFER_TASK", value=task_request.query),
            client.V1EnvVar(
                name="OPENAI_API_KEY",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        name="openai-api-key-secret", # Name of the K8s secret
                        key="OPENAI_API_KEY"          # Key within the secret
                    )
                )
            ),
            client.V1EnvVar(name="PYTHONUNBUFFERED", value="1"),
            # Assuming PLAYWRIGHT_WS_ENDPOINT will be configured within the job runner image
            # or not needed if it runs its own Playwright instance.
        ],
        resources=client.V1ResourceRequirements(
            requests={"cpu": "0.5", "memory": "512Mi"},
            limits={"cpu": "1", "memory": "2Gi"}
        )
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels={"app": "news-surfer-runner", "task_id": task_id}),
        spec=client.V1PodSpec(restart_policy="Never", containers=[container])
    )

    job_spec = client.V1JobSpec(
        template=template,
        backoff_limit=1, # Number of retries before marking job as failed
        ttl_seconds_after_finished=3600 # Clean up finished jobs after 1 hour
    )

    job_body = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name, labels={"task_id": task_id}),
        spec=job_spec
    )

    try:
        batch_v1.create_namespaced_job(body=job_body, namespace="default")
        task_to_job_map[task_id] = job_name
        return NewsTaskResponse(task_id=task_id, message="News summarization task submitted.")
    except ApiException as e:
        # Log the full error for debugging
        print(f"Kubernetes API Exception when creating job: {e.reason} - {e.body}")
        raise HTTPException(status_code=500, detail=f"Error submitting job to Kubernetes: {e.reason}")


@app.get("/news_task/status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    job_name = task_to_job_map.get(task_id)
    if not job_name:
        raise HTTPException(status_code=404, detail="Task ID not found.")

    try:
        job_status_obj = batch_v1.read_namespaced_job_status(name=job_name, namespace="default")
        status_str = get_job_status_string(job_status_obj.status)

        message = None
        if status_str == "Failed":
            # Try to get a reason for failure from conditions
            if job_status_obj.status and job_status_obj.status.conditions:
                for cond in job_status_obj.status.conditions:
                    if cond.type == "Failed" and cond.status == "True":
                        message = cond.message
                        break
            if not message:
                 message = "Job failed without a specific message in conditions."

        return TaskStatusResponse(task_id=task_id, status=status_str, job_name=job_name, message=message)
    except ApiException as e:
        if e.status == 404:
            # If job is not found by K8s API, it might be still pending creation or already cleaned up
            return TaskStatusResponse(task_id=task_id, status="Pending/Unknown", job_name=job_name, message="Job not found in Kubernetes, may be pending or cleaned up.")
        print(f"Kubernetes API Exception when reading job status: {e.reason} - {e.body}")
        raise HTTPException(status_code=500, detail=f"Error getting job status from Kubernetes: {e.reason}")


@app.get("/news_task/result/{task_id}", response_model=NewsResultResponse)
async def get_task_result(task_id: str):
    job_name = task_to_job_map.get(task_id)
    if not job_name:
        raise HTTPException(status_code=404, detail="Task ID not found.")

    try:
        job_status_obj = batch_v1.read_namespaced_job_status(name=job_name, namespace="default")
        status_str = get_job_status_string(job_status_obj.status)

        if status_str == "Succeeded":
            # Job succeeded, try to fetch logs
            job_uid = job_status_obj.metadata.uid # Get UID of the job

            # Find pod associated with the job using the controller-uid label
            pods = core_v1.list_namespaced_pod(
                namespace="default",
                label_selector=f"controller-uid={job_uid}"
            )

            if not pods.items:
                return NewsResultResponse(task_id=task_id, error="Job succeeded but pod logs are not available (pod not found).")

            pod_name = pods.items[0].metadata.name # Assuming one pod per job for this setup

            # Fetch logs from the 'news-surfer-runner' container
            pod_logs = core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace="default",
                container="news-surfer-runner" # Name of the container in the Job spec
            )

            # Process logs: Assume summary is the last non-empty line
            log_lines = pod_logs.strip().split('\n')
            summary = log_lines[-1] if log_lines and log_lines[-1] else "Summary not found in logs."
            return NewsResultResponse(task_id=task_id, summary=summary)

        elif status_str == "Failed":
            # Try to get a reason for failure from conditions for the result
            failure_message = "Job failed."
            if job_status_obj.status and job_status_obj.status.conditions:
                for cond in job_status_obj.status.conditions:
                    if cond.type == "Failed" and cond.status == "True":
                        failure_message = cond.message or failure_message
                        break
            return NewsResultResponse(task_id=task_id, error=failure_message)

        else: # Running, Pending, or Unknown
            return NewsResultResponse(task_id=task_id, error=f"Task is still {status_str}. Please try again later.")

    except ApiException as e:
        if e.status == 404: # Job or Pod not found
             return NewsResultResponse(task_id=task_id, error="Job or associated pod not found. It might have been cleaned up or is still pending.")
        print(f"Kubernetes API Exception when getting job result: {e.reason} - {e.body}")
        raise HTTPException(status_code=500, detail=f"Error getting job result from Kubernetes: {e.reason}")

# Example of how to run this app:
# uvicorn main:app --reload --port 8000
# Ensure your KUBECONFIG is set up if running locally,
# or that the app has appropriate RBAC permissions if running in-cluster.
# Also, ensure the 'openai-api-key-secret' Kubernetes secret exists in the 'default' namespace.
# kubectl create secret generic openai-api-key-secret --from-literal=OPENAI_API_KEY='your_actual_api_key'
```
