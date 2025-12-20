# Quiz Configuration

Quizzes allow testing user knowledge within chat rooms.

## Quick Start

```yaml
# rooms/training/room_config.yaml
quizzes:
  - id: "intro"
    title: "Introduction Quiz"
    question_file: "./quizzes/intro.json"
```

## Configuration Reference

### id (required)

Unique quiz identifier:

```yaml
id: "intro_quiz"
```

### title (required)

Display name for the quiz:

```yaml
title: "Introduction to RAG"
```

### question_file (required)

Path to JSON file containing questions:

```yaml
question_file: "./quizzes/intro.json"
```

Path is relative to the room configuration file.

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

## Question File Format

```json
{
  "questions": [
    {
      "id": "q1",
      "text": "What does RAG stand for?",
      "type": "multiple_choice",
      "options": [
        {"id": "a", "text": "Retrieval-Augmented Generation"},
        {"id": "b", "text": "Random Access Gateway"},
        {"id": "c", "text": "Resource Allocation Guide"}
      ],
      "correct": "a",
      "explanation": "RAG stands for Retrieval-Augmented Generation."
    },
    {
      "id": "q2",
      "text": "What is the primary purpose of embeddings?",
      "type": "multiple_choice",
      "options": [
        {"id": "a", "text": "Text compression"},
        {"id": "b", "text": "Semantic similarity search"},
        {"id": "c", "text": "Data encryption"}
      ],
      "correct": "b"
    }
  ]
}
```

## Question Types

### Multiple Choice

```json
{
  "id": "q1",
  "text": "Which database does Soliplex use for vector storage?",
  "type": "multiple_choice",
  "options": [
    {"id": "a", "text": "PostgreSQL"},
    {"id": "b", "text": "LanceDB"},
    {"id": "c", "text": "MongoDB"}
  ],
  "correct": "b"
}
```

### True/False

```json
{
  "id": "q2",
  "text": "Soliplex supports multiple LLM providers.",
  "type": "true_false",
  "correct": true
}
```

### Free Text

```json
{
  "id": "q3",
  "text": "What command starts the Soliplex server?",
  "type": "free_text",
  "correct": ["soliplex-cli serve", "soliplex-cli serve installation.yaml"]
}
```

## Room Configuration

### Single Quiz

```yaml
quizzes:
  - id: "intro"
    title: "Introduction Quiz"
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

### GET /v1/rooms/{room_id}/quizzes

List available quizzes:

```json
[
  {
    "id": "intro",
    "title": "Introduction Quiz"
  },
  {
    "id": "advanced",
    "title": "Advanced Topics"
  }
]
```

### GET /v1/rooms/{room_id}/quizzes/{quiz_id}

Get quiz details and questions:

```json
{
  "id": "intro",
  "title": "Introduction Quiz",
  "questions": [
    {
      "id": "q1",
      "text": "What does RAG stand for?",
      "type": "multiple_choice",
      "options": [...]
    }
  ]
}
```

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
    Encourage them to take the quizzes.

quizzes:
  - id: "basics"
    title: "Soliplex Basics"
    question_file: "./quizzes/basics.json"
    max_questions: 10

  - id: "rag_deep_dive"
    title: "RAG Deep Dive"
    question_file: "./quizzes/rag.json"
    randomize: true

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
  "questions": [
    {
      "id": "q1",
      "text": "What framework does Soliplex use for agents?",
      "type": "multiple_choice",
      "options": [
        {"id": "a", "text": "LangChain"},
        {"id": "b", "text": "Pydantic AI"},
        {"id": "c", "text": "LlamaIndex"}
      ],
      "correct": "b",
      "explanation": "Soliplex uses Pydantic AI for agent orchestration."
    },
    {
      "id": "q2",
      "text": "What is the default LLM provider?",
      "type": "multiple_choice",
      "options": [
        {"id": "a", "text": "OpenAI"},
        {"id": "b", "text": "Ollama"},
        {"id": "c", "text": "Anthropic"}
      ],
      "correct": "b",
      "explanation": "Ollama is the default provider for local LLM inference."
    },
    {
      "id": "q3",
      "text": "MCP stands for Model Context Protocol.",
      "type": "true_false",
      "correct": true
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
- Quiz endpoints: `src/soliplex/views/quizzes.py`
