MP4_SIGNATURE = b"ftypisom" + b"\x00" * 100


class TestTaskCreation:
    def test_create_processing_task(self, client, test_user, auth_headers, db_session):
        file_content = MP4_SIGNATURE
        files = {"file": ("task_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1
        assert tasks[0]["ffmpeg_command"] is not None

    def test_create_task_with_invalid_file(self, client, test_user, auth_headers):
        payload = {
            "files": ["99999"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload, headers=auth_headers)

        assert response.status_code == 404

    def test_create_task_without_auth(self, client):
        payload = {
            "files": ["1"],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        response = client.post("/api/process", json=payload)

        assert response.status_code == 401


class TestTaskList:
    def test_get_empty_task_list(self, client, test_user, auth_headers):
        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_task_list_with_tasks(
        self, client, test_user, auth_headers, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("tasklist_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        assert process_response.status_code == 200

        response = client.get("/api/tasks", headers=auth_headers)

        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1

    def test_get_task_list_pagination(self, client, test_user, auth_headers):
        response = client.get("/api/tasks?skip=0", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestTaskStatus:
    def test_get_task_status(self, client, test_user, auth_headers, db_session):
        file_content = MP4_SIGNATURE
        files = {"file": ("status_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        response = client.get(f"/api/task-status/{task_id}", headers=auth_headers)

        assert response.status_code == 200
        task = response.json()
        assert task["id"] == task_id
        assert task["status"] in ["pending", "processing", "completed", "failed"]

    def test_get_other_user_task_status(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("u1_task.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        response = client.get(f"/api/task-status/{task_id}", headers=auth_headers_2)

        assert response.status_code == 404

    def test_get_nonexistent_task_status(self, client, test_user, auth_headers):
        response = client.get("/api/task-status/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_task_status_without_auth(self, client):
        response = client.get("/api/task-status/1")

        assert response.status_code == 401


class TestTaskDeletion:
    def test_delete_task(self, client, test_user, auth_headers, db_session):
        file_content = MP4_SIGNATURE
        files = {"file": ("delete_task_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers)

        assert response.status_code == 204

        status_response = client.get(
            f"/api/task-status/{task_id}", headers=auth_headers
        )
        assert status_response.status_code == 404

    def test_delete_other_user_task(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("protected_task.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        payload = {
            "files": [str(file_id)],
            "container": "mp4",
            "startTime": 0,
            "endTime": 100,
            "totalDuration": 100,
            "videoCodec": "libx264",
            "audioCodec": "aac",
            "useHardwareAcceleration": False,
            "preset": "balanced",
        }

        process_response = client.post(
            "/api/process", json=payload, headers=auth_headers
        )
        task_id = process_response.json()[0]["id"]

        response = client.delete(f"/api/tasks/{task_id}", headers=auth_headers_2)

        assert response.status_code == 403

    def test_delete_nonexistent_task(self, client, test_user, auth_headers):
        response = client.delete("/api/tasks/99999", headers=auth_headers)

        assert response.status_code == 204

    def test_delete_task_without_auth(self, client):
        response = client.delete("/api/tasks/1")

        assert response.status_code == 401
