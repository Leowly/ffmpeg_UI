# Project Overview

This project aims to develop a cloud-based FFmpeg application with a user-friendly interface. The goal is to encapsulate the complex functionalities of FFmpeg and leverage the power of cloud computing to provide efficient and convenient audio and video processing services to users.

The project has the following objectives:

1.  Design and implement a stable and efficient cloud-based backend service responsible for file management, user authentication, and FFmpeg task scheduling.
2.  Develop a user-friendly frontend interface that allows users to easily upload, manage, and preview audio and video files, and select various FFmpeg processing operations.
3.  Integrate core FFmpeg functionalities in the cloud, supporting common operations such as transcoding, trimming, merging, and adding watermarks to audio and video files.
4.  Explore and implement cross-platform technology based on Vue.js to adapt and package the web-based prototype into a client application.

The development of this project has the following significance:

1.  **Lowers the technical barrier:** The graphical user interface and cloud-based services make it easy for ordinary users to perform professional audio and video editing and conversion, greatly expanding the popularity and application of FFmpeg technology.
2.  **Improves processing efficiency and user experience:** By offloading time-consuming tasks to the cloud, the project solves the problem of insufficient computing power on mobile devices, which not only significantly improves processing speed but also extends the battery life of mobile devices and improves user experience.
3.  **Explores a new paradigm of combining mobile and cloud:** This project will explore new methods for implementing complex computing tasks on mobile devices, providing a reference and practical experience for the effective combination of mobile frontends and cloud backends in future mobile application development.
4.  **Promotes technical exchange and learning:** The backend and frontend code of this project will be open-sourced to provide a platform for researchers and students in related fields to learn, reference, and carry out secondary development, which will help promote the development of audio and video processing and cross-platform mobile development technologies.

## Backend

The backend is a FastAPI application that handles user authentication, file uploads, and FFmpeg processing. It uses SQLAlchemy for database interaction and JWT for authentication. The backend exposes a RESTful API that the frontend consumes.

## Frontend

The frontend is a Vue.js application built with Vite. It uses Pinia for state management, Vue Router for routing, and Ant Design Vue for UI components. The frontend provides a user-friendly interface for uploading files, viewing file information, and initiating processing tasks.

# Building and Running

## Backend

1.  **Navigate to the backend directory:**

    ```sh
    cd backend
    ```

2.  **Install dependencies:**

    ```sh
    pip install -r requirements.txt
    ```

3.  **Run the development server:**
    ```sh
    uvicorn main:app --reload
    ```

The backend will be running at `http://127.0.0.1:8000`.

## Frontend

1.  **Navigate to the frontend directory:**

    ```sh
    cd frontend
    ```

2.  **Install dependencies:**

    ```sh
    npm install
    ```

3.  **Run the development server:**
    ```sh
    npm run dev
    ```

The frontend will be running at `http://localhost:5173`.

# Development Conventions

## Backend

The backend code is not formatted with a specific tool, but it follows the general Python PEP 8 style guide.

## Frontend

The frontend code is formatted with Prettier and linted with ESLint.

- **To format the code, run:**

  ```sh
  npm run format
  ```

- **To lint the code, run:**
  ```sh
  npm run lint
  ```

# Key Files

## Backend

- `main.py`: The entry point of the FastAPI application. It defines the API endpoints and application logic.
- `database.py`: Configures the database connection and session management.
- `models.py`: Defines the SQLAlchemy database models.
- `schemas.py`: Defines the Pydantic schemas for data validation and serialization.
- `crud.py`: Contains the functions for creating, reading, updating, and deleting data from the database.
- `security.py`: Handles user authentication and password hashing.
- `pyproject.toml`: Defines the project dependencies and metadata.

## Frontend

- `index.html`: The main HTML file of the application.
- `src/main.ts`: The entry point of the Vue.js application.
- `src/App.vue`: The root component of the Vue.js application.
- `src/router/index.ts`: Defines the application routes.
- `src/stores/`: Contains the Pinia stores for state management.
- `src/components/`: Contains the reusable Vue.js components.
- `package.json`: Defines the project dependencies and scripts.
- `vite.config.ts`: The configuration file for Vite.

# Project Structure

```
.
├── backend
│   ├── main.py
│   ├── crud.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── security.py
│   └── pyproject.toml
├── frontend
│   ├── src
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── components
│   │   └── stores
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
└── GEMINI.md
```

# Database Models

The application uses a relational database with two tables: `users` and `files`.

## `users` table

| Column          | Type    | Constraints     | Description                         |
| --------------- | ------- | --------------- | ----------------------------------- |
| id              | Integer | Primary Key     | The unique identifier for the user. |
| username        | String  | Unique, Indexed | The user's username.                |
| hashed_password | String  |                 | The user's hashed password.         |

## `files` table

| Column   | Type    | Constraints            | Description                                                                        |
| -------- | ------- | ---------------------- | ---------------------------------------------------------------------------------- |
| id       | Integer | Primary Key            | The unique identifier for the file.                                                |
| filename | String  | Indexed                | The original name of the uploaded file.                                            |
| filepath | String  | Unique, Indexed        | The path to the file on the server.                                                |
| owner_id | Integer | Foreign Key (users.id) | The ID of the user who uploaded the file.                                          |
| status   | String  |                        | The processing status of the file (e.g., uploaded, processing, completed, failed). |

# API Endpoints

The backend provides the following API endpoints:

## Users

- `POST /token`: Authenticate a user and get an access token.
- `POST /users/`: Create a new user.
- `GET /users/me`: Get the current logged-in user's information.

## Files

- `GET /api/files`: Get a list of all files uploaded by the current user.
- `POST /api/upload`: Upload a new file.
- `GET /api/file-info`: Get information about a specific file.
- `GET /api/download-file/{file_id}`: Download a specific file.
- `POST /api/process`: Process one or more files with FFmpeg.
- `GET /api/task-status/{taskId}`: Get the status of a processing task.
- `DELETE /api/delete-file`: Delete a specific file.

# Frontend Components

The frontend is built with Vue.js and uses the following components:

- `AppSidebar.vue`: A sidebar component that allows users to upload files and displays a list of uploaded files.
- `AuthForm.vue`: A component that provides a user interface for both login and registration.
- `ExportModal.vue`: A modal component that allows users to configure and start the FFmpeg processing. It provides options for video and audio codecs, bitrates, and resolution, and shows a preview of the FFmpeg command that will be executed.
- `SingleFileWorkspace.vue`: The main component for interacting with a selected file. It displays detailed information about the file, allows the user to trim the video or audio, and provides an "Export" button that opens the `ExportModal`.

# State Management (Pinia)

The frontend uses Pinia for state management. The following stores are available:

- `authStore.ts`: Manages user authentication, including login, logout, and registration. It also stores the user's token and information.
- `fileStore.ts`: Manages the file list and the currently selected file. It provides actions to select, fetch, add, and remove files.
