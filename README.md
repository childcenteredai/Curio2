# ChatCompletion Version of Curio2

A conversational AI system built with Flask backend and Vue.js frontend, designed for interactive storytelling and educational content generation.


## System Architecture

```
ChatCompletion System/
├── backend/              # Flask API server
│   ├── app.py           # Main Flask application
│   ├── database_viewer.py # Database viewer API endpoints
│   ├── knowledge/       # Knowledge graph data
│   ├── prompts/         # AI prompt templates
│   └── requirements.txt
├── frontend/            # Vue.js web application
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   └── package.json
├── docker-compose.yml   # Docker Compose configuration
└── README.md
```

## Prerequisites

- **Python 3.8+** with pip
- **Node.js 16+** with **Yarn** (recommended; the frontend Docker image uses `yarn install --frozen-lockfile`)
- **OpenAI API Key** (for AI functionality)
- **Docker & Docker Compose** (for Docker setup)
- **PostgreSQL** (included in Docker setup, or install separately for local development)

## Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/malcolm-chen/Curio2.git
cd Curio2
```

### 2. Backend Setup

Navigate to the backend directory and set up the Python environment:

#### Option A: Using Python venv (recommended)

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### Option B: Using Anaconda/Conda

```bash
cd backend

# Create conda environment
conda create -n curio2 python=3.8

# Activate conda environment
conda activate curio2

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the `backend/` directory:

```bash
# backend/.env
OPENAI_API_KEY=your_openai_api_key_here
VUE_APP_URL=http://localhost:5173
```
Then, create a `.env` file in the `frontend/` directory:

```bash
# frontend/.env
VITE_VUE_APP_URL=http://localhost:5001
VITE_OPENAI_API_KEY=your_openai_api_key_here
```

**Important**: Replace `your_openai_api_key_here` with your actual OpenAI API key.

### 4. Frontend Setup

Navigate to the frontend directory and install dependencies:

```bash
cd ../frontend

# Install dependencies (use Yarn — matches frontend/Dockerfile)
yarn install
```

## Running the System

### Start the Backend Server

From the `backend/` directory:

```bash
# Make sure your virtual environment is activated
# For venv:
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate   # On Windows

# For conda:
conda activate curio2

# Start the server
python app.py
```

The backend server will start on `http://localhost:5001`

### Start the Frontend Development Server

From the `frontend/` directory:

```bash
yarn dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. **Open your browser** and navigate to `http://localhost:5173`
2. **Start a conversation** by typing a message in the chat interface

## API Endpoints

The backend provides the following main endpoints:

### Chat & Speech
- `POST /api/chat` - Send messages and receive AI responses
- `POST /api/speech` - Generate speech audio from text

### Database Viewer (for viewing/downloading conversation data)
- `GET /api/conversations` - List all conversations (supports `limit`, `offset`, `session_id`, `phenomenon` query params)
- `GET /api/conversations/<conversation_id>` - Get detailed conversation with all messages
- `GET /api/conversations/<conversation_id>/messages/<message_id>/audio` - Download audio file for a message
- `GET /api/export` - Export all conversation data (supports `format=json` or `format=csv` query param)
- `GET /api/stats` - Get database statistics

## Configuration

### Backend Configuration

The system uses several prompt templates located in `backend/prompts/`:

- `greet.txt` - Initial greeting messages
- `scienceqa.txt` - Science Q&A prompts
- `scaffolding.txt` - Educational scaffolding prompts
- `reflection.txt` - Reflection and evaluation prompts
- `knowledge_matching.txt` - Knowledge graph matching

## Running the System

### Start the Backend

```bash
cd backend
# Activate virtual environment
source venv/bin/activate
# Run in development mode
python app.py
```

### Start the Frontend

```bash
cd frontend
# Start development server with hot reload
yarn dev
```

### Building for Production

```bash
# Build frontend
cd frontend
yarn build

# The built files will be in dist/
```

## Docker Setup

The system can be run using Docker Compose, which includes PostgreSQL database setup.

### 1. Environment Configuration

**Required:** Create a `.env` file in the project root directory:

```bash
# .env (in project root)
POSTGRES_USER=curio
POSTGRES_PASSWORD=curio_password
POSTGRES_DB=curio_db
```

**Required:** Create a `backend/.env` file with your OpenAI API key:

```bash
# backend/.env
OPENAI_API_KEY=your_openai_api_key_here
```

**Optional:** If you want to customize the frontend build, you can also set these in the root `.env`:

```bash
# .env (optional frontend variables)
VITE_VUE_APP_URL=http://localhost:5001
VITE_OPENAI_API_KEY=your_openai_api_key_here
```

**Note**: 
- The root `.env` file is used by `docker-compose.yml` to set database credentials via environment variable substitution
- The `backend/.env` file is loaded by the backend service for the OpenAI API key
- The `DATABASE_URL` is automatically constructed by the backend from `POSTGRES_*` environment variables set by docker-compose. You don't need to set it manually.

### 2. Build and Start Services

```bash
# From the project root directory
docker-compose up --build
```

This will:
- Start PostgreSQL database on port 5432
- Start the backend service on port 5001
- Build the frontend with **Yarn** (`frontend/Dockerfile`: `yarn install --frozen-lockfile` then `yarn build`) and serve it via nginx
- Automatically configure `DATABASE_URL` for the backend

### 3. Database URL Configuration

When using Docker, the `DATABASE_URL` is automatically set by docker-compose.yml:

```
postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}
```

The default values are:
- **User**: `curio`
- **Password**: `curio_password`
- **Database**: `curio_db`
- **Host**: `postgres` (Docker service name)

To customize these values, set them in your root `.env` file or directly in `docker-compose.yml`.

### 4. Accessing the Application

- Frontend: http://localhost:80
- Backend API: http://localhost:5001
- PostgreSQL: localhost:5432 (for direct database access)

### 5. Database Persistence

The database data is stored in a Docker volume (`postgres_data`), so your data persists even when containers are stopped.

### 6. Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Using External PostgreSQL Database

If you want to use an external PostgreSQL database instead of the Docker service:

1. Remove or comment out the `postgres` service in `docker-compose.yml`
2. Set `DATABASE_URL` in `backend/.env`:
   ```bash
   DATABASE_URL=postgresql://username:password@host:5432/database_name
   ```
3. Remove the `depends_on` section from the backend service in `docker-compose.yml`