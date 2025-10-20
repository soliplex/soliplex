# Soliplex Overview

Soliplex is an AI-powered Retrieval-Augmented Generation (RAG)
system designed to provide intelligent document search and question-answering
capabilities.

## Architecture

The system consists of three main components:

### 1. Backend Server (`soliplex/`)
- **Technology**: FastAPI with Python 3.13
- **Purpose**: Handles API requests, RAG processing, and AI model integration
- **Features**: 
  - OpenAI API integration
  - Document indexing and retrieval
  - Authentication and authorization
  - Real-time WebSocket communication

### 2. Frontend Client (`gen_ai_client/`)
- **Technology**: Flutter web application
- **Purpose**: Provides user interface for chat and document interaction
- **Features**:
  - Material Design UI
  - Real-time chat interface
  - State management with Riverpod
  - Responsive web design

### 3. Configuration System
- **OIDC Authentication**: Keycloak integration for secure access
- **Room Configuration**: Chat environments and settings
- **Model Configuration**: LLM provider and model settings

## Key Features

- **RAG Capabilities**: Combines document retrieval with AI generation
- **Multiple AI Models**: Support for OpenAI and local models
- **Secure Authentication**: OIDC-based user management  
- **Real-time Chat**: WebSocket-powered interactive communication
- **Document Management**: Upload, index, and search through documents
