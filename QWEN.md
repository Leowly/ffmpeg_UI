# FFmpeg UI Cloud Application

## Project Overview

This project is a cloud-based FFmpeg application with a user-friendly interface, designed to encapsulate the complex functionalities of FFmpeg and leverage the power of cloud computing to provide efficient and convenient audio and video processing services to users.

The project follows modern web application architecture with a clean separation between the frontend and backend components, supporting both web and mobile clients through a unified API.

### Key Objectives

1. Design and implement a stable and efficient cloud-based backend service responsible for file management, user authentication, and FFmpeg task scheduling.
2. Develop a user-friendly frontend interface that allows users to easily upload, manage, and preview audio and video files, and select various FFmpeg processing operations.
3. Integrate core FFmpeg functionalities in the cloud, supporting common operations such as transcoding, trimming, merging, and adding watermarks to audio and video files.
4. Support cross-platform access through web browsers and mobile apps.

### Architecture

The system follows a modern C/S (Client/Server) architecture with the following components:

#### Backend (FastAPI)
- Technologies: Python, FastAPI, SQLAlchemy, JWT authentication
- Features: User authentication, file management, FFmpeg task scheduling, database operations
- Handles: User authentication, file uploads/downloads, FFmpeg processing, task management

#### Frontend (Vue.js)
- Technologies: Vue 3, Vite, TypeScript, Pinia, Ant Design Vue
- Features: User-friendly interface for file management and FFmpeg operations
- Handles: File upload/download, processing configuration, task monitoring

#### Cloud Infrastructure
- Nginx reverse proxy for production deployment
- Asynchronous task processing with background workers
- Database storage for user and file metadata
- File storage for uploaded and processed content
- FFmpeg for audio/video processing

## Building and Running

### Backend

1. Navigate to the backend directory:
   ```sh
   cd backend
   ```

2. Set up virtual environment (recommended):
   ```sh
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
   Or, if using uv:
   ```sh
   uv sync
   ```

4. Run the development server:
   ```sh
   python run.py
   ```
   Or alternatively:
   ```sh
   uvicorn main:app --reload
   ```

The backend will be running at `http://127.0.0.1:8000`.

### Frontend

1. Navigate to the frontend directory:
   ```sh
   cd frontend
   ```

2. Install dependencies:
   ```sh
   npm install
   ```

3. Run the development server:
   ```sh
   npm run dev
   ```

The frontend will be running at `http://localhost:5173`.

## Development Conventions

### Backend

- The backend code follows the general Python PEP 8 style guide
- All API endpoints are documented with FastAPI
- Authentication is handled via JWT tokens
- Database interactions use SQLAlchemy ORM
- File paths are normalized using os.path.normpath

### Frontend

- The frontend code is formatted with Prettier and linted with ESLint
- State management is implemented with Pinia
- Routing is handled with Vue Router
- UI components are from Ant Design Vue

To format the code, run:
```sh
npm run format
```

To lint the code, run:
```sh
npm run lint
```

## Key Files

### Backend

- `run.py`: Entry point for running the application with proper asyncio configuration for Windows
- `main.py`: The main FastAPI application with all API endpoints and application logic
- `database.py`: Database connection and session management configuration
- `models.py`: SQLAlchemy database models definition
- `schemas.py`: Pydantic schemas for data validation and serialization
- `crud.py`: Functions for database operations (create, read, update, delete)
- `security.py`: Authentication and password hashing functions
- `pyproject.toml`: Project dependencies and metadata

### Frontend

- `index.html`: Main HTML entry point of the application
- `src/main.ts`: Vue application entry point with Pinia and Ant Design Vue setup
- `src/App.vue`: Root Vue component
- `src/router/index.ts`: Application routing configuration
- `src/stores/`: Pinia stores for state management (authStore, fileStore)
- `src/components/`: Reusable Vue components
- `src/api/index.ts`: API endpoints configuration
- `package.json`: Project dependencies and scripts
- `vite.config.ts`: Vite build configuration

## Database Models

The application uses a relational database with the following tables:

### `users` table

| Column          | Type    | Constraints     | Description                         |
| --------------- | ------- | --------------- | ----------------------------------- |
| id              | Integer | Primary Key     | The unique identifier for the user. |
| username        | String  | Unique, Indexed | The user's username.                |
| hashed_password | String  |                 | The user's hashed password.         |

### `files` table

| Column   | Type    | Constraints            | Description                                                                        |
| -------- | ------- | ---------------------- | ---------------------------------------------------------------------------------- |
| id       | Integer | Primary Key            | The unique identifier for the file.                                                |
| filename | String  | Indexed                | The original name of the uploaded file.                                            |
| filepath | String  | Unique, Indexed        | The path to the file on the server.                                                |
| owner_id | Integer | Foreign Key (users.id) | The ID of the user who uploaded the file.                                          |
| status   | String  |                        | The processing status of the file (e.g., uploaded, processing, completed, failed). |

## API Endpoints

The backend provides the following API endpoints:

### Users

- `POST /token`: Authenticate a user and get an access token.
- `POST /users/`: Create a new user.
- `GET /users/me`: Get the current logged-in user's information.

### Files

- `GET /api/files`: Get a list of all files uploaded by the current user.
- `POST /api/upload`: Upload a new file.
- `GET /api/file-info`: Get information about a specific file.
- `GET /api/download-file/{file_id}`: Download a specific file.
- `POST /api/process`: Process one or more files with FFmpeg.
- `GET /api/task-status/{taskId}`: Get the status of a processing task.
- `DELETE /api/delete-file`: Delete a specific file.

### Tasks

- `GET /api/tasks`: Get all processing tasks for the current user
- `DELETE /api/tasks/{task_id}`: Delete a specific task record

## Frontend Components

The frontend is built with Vue.js and uses the following key components:

- `AppSidebar.vue`: A sidebar component that allows users to upload files and displays a list of uploaded files.
- `AuthForm.vue`: A component that provides a user interface for both login and registration.
- `ExportModal.vue`: A modal component that allows users to configure and start the FFmpeg processing. It provides options for video and audio codecs, bitrates, and resolution, and shows a preview of the FFmpeg command that will be executed.
- `SingleFileWorkspace.vue`: The main component for interacting with a selected file. It displays detailed information about the file, allows the user to trim the video or audio, and provides an "Export" button that opens the `ExportModal`.

## State Management (Pinia)

The frontend uses Pinia for state management with the following stores:

- `authStore.ts`: Manages user authentication, including login, logout, and registration. It also stores the user's token and information.
- `fileStore.ts`: Manages the file list and the currently selected file. It provides actions to select, fetch, add, and remove files.

## FFmpeg Processing Architecture

The system implements sophisticated asynchronous FFmpeg processing:

1. When a user initiates a processing task, the frontend sends a request to the backend
2. The backend creates a database task record and adds it to a processing queue
3. Background tasks execute the FFmpeg commands while updating progress in the database
4. Users can monitor task progress through the frontend's polling mechanism
5. After processing completes, the output file is made available for download

The system includes robust error handling, progress tracking, and file path management.