# Use the official Python base image
FROM python:3.12-slim

# Set working directory to standard /code initially
WORKDIR /code

# Copy the requirements file and install dependencies early (for caching layer)
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Create a non-root user (id 1000) for security. 
# Hugging Face explicitly requires applications to run as a non-root user with ID 1000
RUN useradd -m -u 1000 user

# Switch execution strictly to this new internal user
USER user

# Set up the internal environment variables required by Hugging Face OS
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Move the working directory inside the newly protected user's home folder
WORKDIR $HOME/app

# Copy the entire application code over, explicitly changing ownership to avoid root-only permission blocks
COPY --chown=user . $HOME/app

# Initialize the server
# Hugging Face strictly requires the application to expose and listen directly on port 7860!
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
