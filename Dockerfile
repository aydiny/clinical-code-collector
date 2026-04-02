# Use an official, lightweight Python image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy your requirements file first (this caches dependencies so builds are faster)
COPY requirements.txt .

# Install the Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your actual code into the container
COPY . .

# Expose the port Streamlit uses
EXPOSE 8501

# Command to run the Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]