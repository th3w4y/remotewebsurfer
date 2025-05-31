# 1. Base Image
# Choose a Python version. Python 3.9 is a good default.
# Using a slim variant for a smaller image size.
FROM python:3.9-slim

# 2. Set Working Directory
WORKDIR /app

# 3. Copy requirements and install dependencies
# Copy requirements.txt first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy application code
COPY main.py .
# If there were other modules or static files, they would be copied here too.
# For example: COPY ./app /app/app

# 5. Expose the port the app runs on
EXPOSE 8000

# 6. Command to run the application
# Using 0.0.0.0 so it's accessible from outside the container within the K8s pod.
# The --reload flag is typically not used in production images.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
