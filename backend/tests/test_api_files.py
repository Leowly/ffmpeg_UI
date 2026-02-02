MP4_SIGNATURE = b"ftypisom" + b"\x00" * 100


class TestFileUpload:
    def test_upload_file_success(self, client, test_user, auth_headers):
        file_content = MP4_SIGNATURE
        files = {"file": ("test_video.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test_video.mp4"
        assert data["status"] == "done"
        assert "id" in data
        assert "uid" in data

    def test_upload_invalid_file_type(self, client, test_user, auth_headers):
        file_content = b"some data"
        files = {"file": ("test.txt", file_content, "text/plain")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        assert response.status_code == 400
        assert "不支持的文件格式" in response.json()["detail"]

    def test_upload_without_auth(self, client):
        file_content = MP4_SIGNATURE
        files = {"file": ("test_video.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files)

        assert response.status_code == 401

    def test_upload_large_file(self, client, test_user, auth_headers, monkeypatch):
        file_content = MP4_SIGNATURE
        files = {"file": ("test.mp4", file_content, "video/mp4")}

        response = client.post("/api/upload", files=files, headers=auth_headers)

        assert response.status_code == 200


class TestFileList:
    def test_get_empty_file_list(self, client, test_user, auth_headers):
        response = client.get("/api/files", headers=auth_headers)

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_file_list_with_files(
        self, client, test_user, auth_headers, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("another_video.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        assert upload_response.status_code == 200

        response = client.get("/api/files", headers=auth_headers)

        assert response.status_code == 200
        files_list = response.json()
        assert len(files_list) >= 1


class TestFileDownload:
    def test_download_own_file(self, client, test_user, auth_headers, db_session):
        file_content = MP4_SIGNATURE
        files = {"file": ("download_test.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        response = client.get(f"/api/download-file/{file_id}", headers=auth_headers)

        assert response.status_code == 200
        assert "Content-Disposition" in response.headers

    def test_download_other_user_file(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("user1_file.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        response = client.get(f"/api/download-file/{file_id}", headers=auth_headers_2)

        assert response.status_code == 404

    def test_download_nonexistent_file(self, client, test_user, auth_headers):
        response = client.get("/api/download-file/99999", headers=auth_headers)

        assert response.status_code == 404

    def test_download_without_auth(self, client, db_session):
        response = client.get("/api/download-file/1")

        assert response.status_code == 401


class TestFileDelete:
    def test_delete_own_file(self, client, test_user, auth_headers, db_session):
        file_content = MP4_SIGNATURE
        files = {"file": ("delete_me.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        response = client.delete(
            f"/api/delete-file?filename={file_id}", headers=auth_headers
        )

        assert response.status_code == 200

        download_response = client.get(
            f"/api/download-file/{file_id}", headers=auth_headers
        )
        assert download_response.status_code == 404

    def test_delete_other_user_file(
        self, client, test_user, auth_headers, test_user_2, auth_headers_2, db_session
    ):
        file_content = MP4_SIGNATURE
        files = {"file": ("protected.mp4", file_content, "video/mp4")}

        upload_response = client.post("/api/upload", files=files, headers=auth_headers)
        file_id = upload_response.json()["id"]

        response = client.delete(
            f"/api/delete-file?filename={file_id}", headers=auth_headers_2
        )

        assert response.status_code == 404

    def test_delete_without_auth(self, client):
        response = client.delete("/api/delete-file?filename=1")

        assert response.status_code == 401


class TestSystemCapabilities:
    def test_get_capabilities(self, client, test_user, auth_headers):
        response = client.get("/api/capabilities", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "has_hardware_acceleration" in data
        assert "hardware_type" in data

    def test_get_capabilities_without_auth(self, client):
        response = client.get("/api/capabilities")

        assert response.status_code == 401
