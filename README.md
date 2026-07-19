# OwnGPT

OwnGPT is a fully-featured, local generative AI chatbot application. It features a modern, glowing UI inspired by Gemini and ChatGPT, powered by a robust Python backend utilizing LangGraph and FastAPI. 

## Features

- **Modern Chat Interface**: Built with React, Vite, TailwindCSS, and Shadcn UI. Features a floating glowing chat input bar and a beautiful dark mode aesthetic.
- **Retrieval-Augmented Generation (RAG)**: Upload PDF, TXT, or Markdown files. Documents are automatically chunked, embedded, and stored in a local PostgreSQL `pgvector` database. The agent can dynamically search your knowledge base to provide cited answers.
- **Multimodal Vision**: Native support for image uploads. Attach images to your messages and the LLM (like GPT-4o) can analyze and describe them.
- **Tool Calling & Agentic Workflows**: Built on LangGraph, the agent can autonomously decide when to use tools such as Web Search or Knowledge Base queries.
- **Real-Time Streaming**: Fast, token-by-token Server-Sent Events (SSE) streaming for a responsive user experience.
- **Dockerized Setup**: Fully containerized using Docker Compose for seamless development and deployment.

## Tech Stack

### Frontend
- React 18 & Vite
- TailwindCSS & Framer Motion
- Shadcn UI & Lucide Icons
- React Markdown (for rich text formatting and code blocks)

### Backend
- FastAPI & Uvicorn
- LangChain & LangGraph
- PostgreSQL with `pgvector` (via `langchain-postgres`)
- OpenAI API (for embeddings and language models)

## Getting Started

### Prerequisites
- Docker and Docker Compose
- An OpenAI API Key (or compatible API key for the models configured in `.env`)

### Installation & Running Locally

1. **Clone the repository**:
   ```bash
   git clone https://github.com/lightsspeed/own-gpt.git
   cd own-gpt
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory and add your API keys.
   ```env
   OPENAI_API_KEY=your_openai_api_key
   TAVILY_API_KEY=your_tavily_api_key_for_web_search
   ```

3. **Start the application using Docker Compose**:
   ```bash
   docker-compose up --build
   ```

4. **Access the Application**:
   - Frontend UI: http://localhost:5173
   - Backend API Docs: http://localhost:8000/docs
   - Database: PostgreSQL running on port 5432

## Project Structure

- `/frontend` - React/Vite frontend application
- `/app` - FastAPI application and LangGraph agent logic
  - `/api` - REST endpoints (chat streaming, document upload)
  - `/agent` - LangGraph nodes, state definitions, and tools
  - `/models` - SQLAlchemy database models
  - `/services` - pgvector integration and utility services

## License
MIT License
