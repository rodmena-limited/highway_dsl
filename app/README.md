# Highway DSL Generator API

A standalone Flask API that generates valid Highway DSL workflows from natural language descriptions using Ollama LLM.

## Quick Start

### 1. Install Dependencies

```bash
cd app
pip install -r requirements.txt
```

### 2. Ensure Ollama is Running

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Pull the model if needed
ollama pull deepseek-v3.1:671b-cloud
```

### 3. Start the API

```bash
python app.py
```

The API will be available at `http://localhost:7291`

## Usage

### Generate a Workflow

```bash
curl -G "http://localhost:7291/api/v1/generate_dsl" \
  --data-urlencode "input=Create a simple workflow that downloads data from an API and saves it to a file"
```

### Health Check

```bash
curl http://localhost:7291/health
```

## Example

```bash
# Generate workflow and save to file
curl -G "http://localhost:7291/api/v1/generate_dsl" \
  --data-urlencode "input=Create a workflow that fetches user data from https://api.example.com/users, processes each user, and sends them an email" \
  -o workflow.py

# Verify it's valid Python
python3 -m py_compile workflow.py

# Execute to generate JSON
python3 workflow.py > workflow.json
```

## Configuration

Set environment variable to use a different Ollama server:

```bash
export OLLAMA_BASE_URL=http://your-ollama-server:11434
python app.py
```

## API Endpoints

- `GET /api/v1/generate_dsl?input=<description>` - Generate workflow
- `GET /health` - Health check
- `GET /` - API documentation

## Files

- `app.py` - Flask application
- `AGENT_PROMPT.md` - LLM system prompt with Highway DSL documentation
- `requirements.txt` - Python dependencies
- `README.md` - This file
