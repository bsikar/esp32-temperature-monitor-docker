# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir reduces image size
# --trusted-host pypi.python.org and --trusted-host pypi.org can help in some network environments
RUN pip install --no-cache-dir --trusted-host pypi.python.org --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy the rest of the application code (., meaning current directory) into the container at /app
COPY . .

# Make the run script executable
RUN chmod +x /app/run.sh

# Make port 5000 available to the world outside this container (the Flask app's port)
EXPOSE 5000

# Define the command to run your application
CMD ["/app/run.sh"]
