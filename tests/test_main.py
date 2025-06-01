import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
import uuid

# Ensure the app can be imported.
try:
    from kubernetes.client.rest import ApiException
    import main as main_module
    from main import NewsTaskRequest, NewsTaskResponse, TaskStatusResponse, NewsResultResponse # Import models
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from kubernetes.client.rest import ApiException
    import main as main_module
    from main import NewsTaskRequest, NewsTaskResponse, TaskStatusResponse, NewsResultResponse


client = TestClient(main_module.app)

@pytest.fixture(autouse=True)
def clear_task_map_and_reload_main():
    """Fixture to clear the task_to_job_map before each test and reload module."""
    main_module.task_to_job_map.clear()
    # No need to reload main_module for these tests as K8s client is mocked globally in main.py
    # If K8s client init was per-function or needed env var changes, reload would be needed.


# --- Mock Kubernetes Objects Helpers ---
def get_mock_v1_job_status(succeeded=0, failed=0, active=0, conditions=None):
    status = MagicMock(spec=main_module.client.V1JobStatus)
    status.succeeded = succeeded
    status.failed = failed
    status.active = active
    status.conditions = conditions if conditions is not None else []
    return status

def get_mock_v1_job(uid, status_obj):
    job = MagicMock(spec=main_module.client.V1Job)
    job.metadata = MagicMock(spec=main_module.client.V1ObjectMeta, uid=uid)
    job.status = status_obj
    return job

# --- Tests for POST /news_task ---

@patch('main.batch_v1', autospec=True)
def test_submit_news_task_success(mock_batch_v1_api, clear_task_map_and_reload_main):
    mock_batch_v1_api.create_namespaced_job = MagicMock()

    query = "Summarize OpenAI news"
    response = client.post("/news_task", json={"query": query})

    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["message"] == "News summarization task submitted."
    task_id = data["task_id"]

    assert task_id in main_module.task_to_job_map
    job_name_expected_prefix = f"news-surfer-job-{task_id[:8]}"
    assert main_module.task_to_job_map[task_id].startswith(job_name_expected_prefix)

    mock_batch_v1_api.create_namespaced_job.assert_called_once()
    call_args = mock_batch_v1_api.create_namespaced_job.call_args
    job_body = call_args.kwargs['body']

    assert job_body.kind == "Job"
    assert job_body.metadata.name.startswith(job_name_expected_prefix)
    assert job_body.spec.template.spec.containers[0].name == "news-surfer-runner"
    assert job_body.spec.template.spec.containers[0].image == "your-container-registry/news-job-runner:latest"

    env_vars = {env.name: env for env in job_body.spec.template.spec.containers[0].env}
    assert env_vars["WEBSURFER_TASK"].value == query
    assert env_vars["OPENAI_API_KEY"].value_from.secret_key_ref.name == "openai-api-key-secret"
    assert env_vars["OPENAI_API_KEY"].value_from.secret_key_ref.key == "OPENAI_API_KEY"

@patch('main.batch_v1', autospec=True)
def test_submit_news_task_k8s_api_error(mock_batch_v1_api, clear_task_map_and_reload_main):
    mock_batch_v1_api.create_namespaced_job.side_effect = ApiException(status=500, reason="K8s internal error")

    response = client.post("/news_task", json={"query": "Test query for K8s error"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Error submitting job to Kubernetes: K8s internal error"}

# --- Tests for GET /news_task/status/{task_id} ---

def test_get_task_status_not_found(clear_task_map_and_reload_main):
    unknown_task_id = str(uuid.uuid4())
    response = client.get(f"/news_task/status/{unknown_task_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task ID not found."}

@patch('main.batch_v1', autospec=True)
def test_get_task_status_succeeded(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_status = get_mock_v1_job_status(succeeded=1)
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "status": "Succeeded", "job_name": job_name, "message": None}
    mock_batch_v1_api.read_namespaced_job_status.assert_called_once_with(name=job_name, namespace="default")

@patch('main.batch_v1', autospec=True)
def test_get_task_status_failed(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    failed_condition = MagicMock()
    failed_condition.type = "Failed"
    failed_condition.status = "True"
    failed_condition.message = "Pod failed due to OOM"
    mock_status = get_mock_v1_job_status(failed=1, conditions=[failed_condition])
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "status": "Failed", "job_name": job_name, "message": "Pod failed due to OOM"}

@patch('main.batch_v1', autospec=True)
def test_get_task_status_running(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_status = get_mock_v1_job_status(active=1)
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "status": "Running", "job_name": job_name, "message": None}

@patch('main.batch_v1', autospec=True)
def test_get_task_status_pending(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    # No active, succeeded, or failed counts typically means pending
    mock_status = get_mock_v1_job_status()
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 200
    # The helper function get_job_status_string returns "Pending/Unknown" for this case
    assert response.json() == {"task_id": task_id, "status": "Pending/Unknown", "job_name": job_name, "message": None}


@patch('main.batch_v1', autospec=True)
def test_get_task_status_k8s_api_error(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_batch_v1_api.read_namespaced_job_status.side_effect = ApiException(status=500, reason="K8s down")

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 500
    assert response.json() == {"detail": "Error getting job status from Kubernetes: K8s down"}

@patch('main.batch_v1', autospec=True)
def test_get_task_status_k8s_job_not_found_yet(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_batch_v1_api.read_namespaced_job_status.side_effect = ApiException(status=404, reason="Not Found")

    response = client.get(f"/news_task/status/{task_id}")
    assert response.status_code == 200 # The endpoint handles 404 from K8s as a valid status
    assert response.json() == {"task_id": task_id, "status": "Pending/Unknown", "job_name": job_name, "message": "Job not found in Kubernetes, may be pending or cleaned up."}


# --- Tests for GET /news_task/result/{task_id} ---

def test_get_task_result_not_found(clear_task_map_and_reload_main):
    unknown_task_id = str(uuid.uuid4())
    response = client.get(f"/news_task/result/{unknown_task_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task ID not found."}

@patch('main.batch_v1', autospec=True)
def test_get_task_result_job_not_succeeded_running(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_status = get_mock_v1_job_status(active=1) # Running
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/result/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "summary": None, "error": "Task is still Running. Please try again later."}

@patch('main.batch_v1', autospec=True)
def test_get_task_result_job_failed(mock_batch_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    failed_condition = MagicMock()
    failed_condition.type = "Failed"; failed_condition.status = "True"; failed_condition.message = "Job pod crashed"
    mock_status = get_mock_v1_job_status(failed=1, conditions=[failed_condition])
    mock_job_obj = get_mock_v1_job(uid=str(uuid.uuid4()), status_obj=mock_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    response = client.get(f"/news_task/result/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "summary": None, "error": "Job pod crashed"}


@patch('main.core_v1', autospec=True)
@patch('main.batch_v1', autospec=True)
def test_get_task_result_success(mock_batch_v1_api, mock_core_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    job_uid = f"uid-{task_id[:8]}"
    pod_name = f"pod-{job_uid[:4]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_job_status = get_mock_v1_job_status(succeeded=1)
    mock_job_obj = get_mock_v1_job(uid=job_uid, status_obj=mock_job_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    mock_pod = MagicMock(spec=main_module.client.V1Pod)
    mock_pod.metadata = MagicMock(spec=main_module.client.V1ObjectMeta, name=pod_name)
    mock_pod_list = MagicMock(spec=main_module.client.V1PodList, items=[mock_pod])
    mock_core_v1_api.list_namespaced_pod.return_value = mock_pod_list

    summary_log = "This is the final summary."
    mock_core_v1_api.read_namespaced_pod_log.return_value = f"Log line 1\nLog line 2\n{summary_log}"

    response = client.get(f"/news_task/result/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "summary": summary_log, "error": None}

    mock_batch_v1_api.read_namespaced_job_status.assert_called_once_with(name=job_name, namespace="default")
    mock_core_v1_api.list_namespaced_pod.assert_called_once_with(namespace="default", label_selector=f"controller-uid={job_uid}")
    mock_core_v1_api.read_namespaced_pod_log.assert_called_once_with(name=pod_name, namespace="default", container="news-surfer-runner")

@patch('main.core_v1', autospec=True)
@patch('main.batch_v1', autospec=True)
def test_get_task_result_success_no_logs(mock_batch_v1_api, mock_core_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    job_uid = f"uid-{task_id[:8]}"
    pod_name = f"pod-{job_uid[:4]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_job_status = get_mock_v1_job_status(succeeded=1)
    mock_job_obj = get_mock_v1_job(uid=job_uid, status_obj=mock_job_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    mock_pod = MagicMock(spec=main_module.client.V1Pod)
    mock_pod.metadata = MagicMock(spec=main_module.client.V1ObjectMeta, name=pod_name)
    mock_pod_list = MagicMock(spec=main_module.client.V1PodList, items=[mock_pod])
    mock_core_v1_api.list_namespaced_pod.return_value = mock_pod_list

    mock_core_v1_api.read_namespaced_pod_log.return_value = "" # Empty logs

    response = client.get(f"/news_task/result/{task_id}")
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "summary": "Summary not found in logs.", "error": None}


@patch('main.core_v1', autospec=True)
@patch('main.batch_v1', autospec=True)
def test_get_task_result_success_no_pod_found(mock_batch_v1_api, mock_core_v1_api, clear_task_map_and_reload_main):
    task_id = str(uuid.uuid4())
    job_name = f"job-{task_id[:8]}"
    job_uid = f"uid-{task_id[:8]}"
    main_module.task_to_job_map[task_id] = job_name

    mock_job_status = get_mock_v1_job_status(succeeded=1)
    mock_job_obj = get_mock_v1_job(uid=job_uid, status_obj=mock_job_status)
    mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job_obj

    mock_core_v1_api.list_namespaced_pod.return_value = MagicMock(spec=main_module.client.V1PodList, items=[]) # No pods

    response = client.get(f"/news_task/result/{task_id}")
    assert response.status_code == 200 # Endpoint handles this as a specific error case, not a 404 on the task
    assert response.json() == {"task_id": task_id, "summary": None, "error": "Job succeeded but pod logs are not available (pod not found)."}
    mock_core_v1_api.read_namespaced_pod_log.assert_not_called()
