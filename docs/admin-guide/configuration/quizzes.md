# Quiz Configuration

Quizzes allow testing user knowledge within chat rooms.

## Quick Start

```yaml
# rooms/training/room_config.yaml
quizzes:
  - id: "intro"
    question_file: "./quizzes/intro.json"
```

## Configuration Reference

### id (required)

Unique quiz identifier:

```yaml
id: "intro_quiz"
```

### question_file (required)

Path to JSON file containing questions:

```yaml
question_file: "./quizzes/intro.json"
```

Path is relative to the room configuration file.

### title

Display name for the quiz. Default: `"Quiz"`

```yaml
title: "Introduction to RAG"
```

### randomize

Randomize question order. Default: `false`

```yaml
randomize: true
```

### max_questions

Limit number of questions. Default: all questions

```yaml
max_questions: 10
```

### judge_agent

Optional agent configuration for evaluating free-form answers:

```yaml
judge_agent:
  model_name: "gpt-oss:latest"
```

## Question File Format

Question files use the Pydantic evals dataset format:

```json
{
  "cases": [
    {
      "inputs": "What does RAG stand for?",
      "expected_output": "Retrieval-Augmented Generation",
      "metadata": {
        "uuid": "q1-unique-id",
        "type": "qa"
      }
    }
  ]
}
```

### Field Reference

| Field | Description |
|-------|-------------|
| `inputs` | The question text shown to the user |
| `expected_output` | The correct answer |
| `metadata.uuid` | Unique identifier for the question |
| `metadata.type` | Question type: `qa`, `fill-blank`, or `multiple-choice` |
| `metadata.options` | Answer options (for `multiple-choice` only) |

## Question Types

### QA (Question & Answer)

Free-form question with expected answer:

```json
{
  "inputs": "What framework does Soliplex use for agents?",
  "expected_output": "Pydantic AI",
  "metadata": {
    "uuid": "58cd4636-9934-427e-b4b7-1678f2e92751",
    "type": "qa"
  }
}
```

### Fill-in-the-Blank

Question with blank to fill:

```json
{
  "inputs": "The default LLM provider is _____",
  "expected_output": "Ollama",
  "metadata": {
    "uuid": "48ee5a26-8d3e-4032-b910-44912b7f13c2",
    "type": "fill-blank"
  }
}
```

### Multiple Choice

Question with predefined options:

```json
{
  "inputs": "Which database does Soliplex use for vector storage?",
  "expected_output": "LanceDB",
  "metadata": {
    "uuid": "8ae8d35a-cab7-4537-a915-2f67b3152a3c",
    "type": "multiple-choice",
    "options": [
      "PostgreSQL",
      "LanceDB",
      "MongoDB"
    ]
  }
}
```

**Note:** The `expected_output` must exactly match one of the `options`.

## Room Configuration

### Single Quiz

```yaml
quizzes:
  - id: "intro"
    question_file: "./quizzes/intro.json"
```

### Multiple Quizzes

```yaml
quizzes:
  - id: "intro"
    title: "Introduction"
    question_file: "./quizzes/intro.json"
    max_questions: 5

  - id: "advanced"
    title: "Advanced Topics"
    question_file: "./quizzes/advanced.json"
    randomize: true
```

## API Endpoints

### GET /v1/rooms/{room_id}/quiz/{quiz_id}

Get quiz details and questions:

```json
{
  "id": "intro",
  "title": "Introduction Quiz",
  "randomize": false,
  "max_questions": null,
  "questions": [
    {
      "inputs": "What does RAG stand for?",
      "expected_output": "Retrieval-Augmented Generation",
      "metadata": {
        "uuid": "q1-unique-id",
        "type": "qa",
        "options": []
      }
    }
  ]
}
```

### POST /v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}

Submit an answer to a quiz question.

**Request body:**
```json
{
  "text": "Retrieval-Augmented Generation"
}
```

**Response:**
```json
{
  "correct": "true",
  "expected_output": "Retrieval-Augmented Generation"
}
```

The `correct` field is a string: `"true"` or `"false"`.

## Complete Example

### Room Configuration

```yaml
# rooms/training/room_config.yaml
id: "training"
name: "Training Room"
description: "Learn about Soliplex with interactive quizzes"

agent:
  model_name: "gpt-oss:latest"
  system_prompt: |
    You are a training assistant.
    Help users learn about Soliplex and RAG.

quizzes:
  - id: "basics"
    title: "Soliplex Basics"
    question_file: "./quizzes/basics.json"
    max_questions: 10

  - id: "rag_deep_dive"
    title: "RAG Deep Dive"
    question_file: "./quizzes/rag.json"
    randomize: true
    judge_agent:
      model_name: "gpt-oss:latest"

welcome_message: |
  Welcome to the Training Room!
  Take our interactive quizzes to test your knowledge.

suggestions:
  - "Start the basics quiz"
  - "Explain how RAG works"
```

### Question File

```json
{
  "cases": [
    {
      "inputs": "What framework does Soliplex use for agents?",
      "expected_output": "Pydantic AI",
      "metadata": {
        "uuid": "q1-framework",
        "type": "qa"
      }
    },
    {
      "inputs": "What is the default LLM provider?",
      "expected_output": "Ollama",
      "metadata": {
        "uuid": "q2-provider",
        "type": "multiple-choice",
        "options": [
          "OpenAI",
          "Ollama",
          "Anthropic"
        ]
      }
    },
    {
      "inputs": "MCP stands for Model Context _____",
      "expected_output": "Protocol",
      "metadata": {
        "uuid": "q3-mcp",
        "type": "fill-blank"
      }
    }
  ]
}
```

## Directory Structure

```
rooms/
└── training/
    ├── room_config.yaml
    └── quizzes/
        ├── basics.json
        └── rag.json
```

## Source Code

- Quiz configuration: `src/soliplex/config.py`
- Quiz logic: `src/soliplex/quizzes.py`
- Quiz endpoints: `src/soliplex/views/quizzes.py`
- Quiz models: `src/soliplex/models.py`
