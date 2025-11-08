# backend/config.py
import os

# --- Global Configurations ---
UPLOAD_DIRECTORY = "./backend/workspaces"

# --- Utility Functions ---
def reconstruct_file_path(stored_path: str, user_id: int) -> str | None:
    # 确保上传目录存在
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
    
    if os.path.exists(stored_path):
        return stored_path
    
    expected_user_dir = os.path.join(UPLOAD_DIRECTORY, str(user_id))
    unique_filename = os.path.basename(stored_path)
    reconstructed_file_path = os.path.join(expected_user_dir, unique_filename)
    
    if os.path.exists(reconstructed_file_path):
        return reconstructed_file_path
        
    return None