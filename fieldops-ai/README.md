# FieldOps AI

> **Context-Aware Technician Dispatch & ETA Prediction Platform**
>
> Enterprise-grade, AI-powered field operations management system built with React 19 + FastAPI.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Frontend Setup](#frontend-setup)
  - [Backend Setup](#backend-setup)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Development Guidelines](#development-guidelines)
- [Contributing](#contributing)

---

## Overview

FieldOps AI is an enterprise-grade platform that leverages artificial intelligence to intelligently dispatch field technicians, predict ETAs, and optimize resource allocation in real time.

---

## Architecture

```
fieldops-ai/
├── frontend/          # React 19 + Vite + TypeScript + Tailwind CSS
├── backend/           # Python 3.12 + FastAPI + SQLAlchemy + Alembic
├── docs/              # Architecture decisions, API specs, diagrams
├── datasets/          # Training data, seed data, fixtures
├── tests/             # Integration & E2E test suites
└── screenshots/       # UI screenshots for documentation
```

---

## Tech Stack

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| React | 19.x | UI framework |
| Vite | 6.x | Build tool & dev server |
| TypeScript | 5.x | Type safety |
| Tailwind CSS | 3.x | Utility-first styling |
| React Router | 7.x | Client-side routing |
| Axios | 1.x | HTTP client |
| TanStack Query | 5.x | Server state management |
| React Hook Form | 7.x | Form management |
| Zod | 3.x | Schema validation |
| Lucide React | latest | Icon library |

### Backend
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12 | Runtime |
| FastAPI | 0.115.x | API framework |
| SQLAlchemy | 2.x | ORM |
| Alembic | 1.x | Database migrations |
| Pydantic | 2.x | Data validation |
| Uvicorn | 0.32.x | ASGI server |
| asyncpg | 0.30.x | Async PostgreSQL driver |

### Database
| Technology | Version | Purpose |
|---|---|---|
| PostgreSQL | 16.x | Primary relational database |

---

## Project Structure

### Frontend (`frontend/src/`)

```
src/
├── assets/            # Static assets (images, fonts, icons)
├── components/        # Reusable UI components
│   └── ui/            # Base design system components
├── config/            # App configuration and constants
├── contexts/          # React context providers
├── hooks/             # Custom React hooks
├── layouts/           # Page layout components
├── pages/             # Route-level page components
├── routes/            # Router configuration
├── services/          # API service layer (Axios)
├── styles/            # Global styles and Tailwind base
├── types/             # TypeScript type definitions
└── utils/             # Pure utility functions
```

### Backend (`backend/app/`)

```
app/
├── api/               # API route handlers
│   └── v1/            # Version 1 endpoints
├── core/              # Core config, logging, exceptions
├── database/          # SQLAlchemy session and base model
├── middleware/         # CORS, logging, auth middleware
├── models/            # SQLAlchemy ORM models
├── repositories/      # Data access layer
├── schemas/           # Pydantic request/response schemas
├── services/          # Business logic layer
└── utils/             # Utility functions
```

---

## Getting Started

### Prerequisites

- **Node.js** >= 20.x
- **Python** >= 3.12
- **PostgreSQL** >= 16.x
- **Git**

### Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Start the development server
npm run dev
```

The frontend dev server starts at **http://localhost:5173**

### Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Start the development server
uvicorn app.main:app --reload
```

The API server starts at **http://localhost:8000**

Interactive API docs available at **http://localhost:8000/docs**

---

## Environment Variables

Copy `.env.example` to `.env` (root, frontend, and backend) and update the values.

| Variable | Description | Default |
|---|---|---|
| `VITE_API_BASE_URL` | Backend API base URL | `http://localhost:8000/api/v1` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `SECRET_KEY` | JWT / encryption secret | *(must be set)* |
| `ALLOWED_ORIGINS` | CORS allowed origins | `http://localhost:5173` |

---

## API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Health Check
```http
GET /api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "FieldOps AI API",
  "version": "1.0.0"
}
```

### Interactive Docs
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## Development Guidelines

- Use **TypeScript strict mode** — no `any` types
- All components must be **functional** React components
- No **inline styles** — use Tailwind utility classes only
- Follow **SOLID principles** in the service and repository layers
- All API responses must be wrapped in a standard **response envelope**
- Use **feature-based** folder organization for new features
- Write **Pydantic schemas** for all request/response models
- Use **async/await** throughout the FastAPI layer

---

## Contributing

1. Create a feature branch from `main`
2. Follow the coding standards above
3. Write tests for new functionality
4. Open a pull request with a clear description

---

*Built with ❤️ — FieldOps AI © 2026*
