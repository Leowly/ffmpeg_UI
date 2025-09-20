import os
import uuid
import shutil
import time
import threading
import json
import subprocess
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session # 👈 1. 导入 Session
from werkzeug.utils import secure_filename

# 初始化 Flask 应用
app = Flask(__name__)

# --- 核心配置修改 ---
# 2. 配置 Flask-Session
app.config['SECRET_KEY'] = 'a-super-secret-key-for-my-ffmpeg-project'
app.config['SESSION_TYPE'] = 'filesystem'  #  session 类型为文件系统
app.config['SESSION_PERMANENT'] = True      # 使 session 永久有效
app.config['SESSION_USE_SIGNER'] = True     # 对 cookie 中的 session_id 进行签名
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_sessions') # session 文件存储目录
app.config['SESSION_COOKIE_SECURE'] = not app.debug 
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
# 3. 初始化 Session
Session(app)
# --------------------

# 配置 CORS
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# 配置上传文件夹
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 用于存储每个 session 的最后活动时间
session_activity = {}
session_lock = threading.Lock()

def get_session_id():
    """获取或创建用户的 session ID"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return session['user_id']

def update_session_activity():
    """更新当前 session 的最后活动时间"""
    user_id = session.get('user_id')
    if user_id:
        with session_lock:
            session_activity[user_id] = time.time()

# --- API 接口 ---

@app.before_request
def before_request_func():
    """在每个请求之前，确保用户有 session ID 并更新活动时间"""
    get_session_id()
    update_session_activity()

@app.route('/api/files', methods=['GET'])
def list_files():
    """列出当前用户的所有文件"""
    user_id = session['user_id']
    print(f"--- Received request for user_id: {user_id} ---") # 打印 session id
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    print(f"--- Checking folder: {user_folder} ---") # 打印检查的文件夹路径
    
    if not os.path.exists(user_folder):
        return jsonify([]) # 如果文件夹不存在，返回空列表

    files_info = []
    for filename in os.listdir(user_folder):
        file_path = os.path.join(user_folder, filename)
        file_id = os.path.splitext(filename)[0]
        files_info.append({
            "uid": file_id, # 使用文件ID作为 uid
            "id": file_id,
            "name": filename,
            "status": "done",
            "size": os.path.getsize(file_path),
            # 为了方便前端，构建一个 response 对象
            "response": {
                "file_id": file_id,
                "original_name": filename,
                "temp_path": file_path
            }
        })
    return jsonify(files_info)

# backend/app.py

@app.route('/api/upload', methods=['POST'])
def upload_file():
    user_id = session['user_id']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    
    # --- 添加日志 ---
    print(f"--- Upload request for user_id: {user_id} ---")
    print(f"--- Target folder: {user_folder} ---")
    
    if not os.path.exists(user_folder):
        try:
            os.makedirs(user_folder)
            print(f"--- Created user folder: {user_folder} ---")
        except Exception as e:
            print(f"!!! ERROR: Failed to create user folder: {e} !!!")
            return jsonify({"error": f"Server error: cannot create directory for user {user_id}"}), 500

    if 'file' not in request.files:
        print("!!! ERROR: 'file' part not in request.files !!!")
        return jsonify({"error": "No file part in the request"}), 400
        
    file = request.files['file']
    
    if file.filename == '':
        print("!!! ERROR: No file selected (filename is empty) !!!")
        return jsonify({"error": "No selected file"}), 400

    if file:
        original_filename = secure_filename(file.filename)
        file_extension = os.path.splitext(original_filename)[1]
        unique_id = str(uuid.uuid4())
        unique_filename = unique_id + file_extension
        save_path = os.path.join(user_folder, unique_filename)
        
        print(f"--- Attempting to save file to: {save_path} ---")
        
        try:
            file.save(save_path)
            print(f"--- SUCCESS: File saved to {save_path} ---")
            
            # 确认文件真的存在
            if os.path.exists(save_path):
                print("--- VERIFIED: File exists on disk after saving. ---")
            else:
                print("!!! CRITICAL ERROR: File.save() did not raise error, but file does not exist! Check permissions or disk space. !!!")

            response_data = {
                "msg": "Upload successful",
                "file_id": unique_id,
                "original_name": original_filename,
                "temp_path": save_path
            }
            return jsonify(response_data), 200
        except Exception as e:
            print(f"!!! ERROR: file.save() failed with exception: {e} !!!")
            return jsonify({"error": f"Server error: failed to save file. Exception: {e}"}), 500

    print("!!! ERROR: Unknown error, request reached end of function without returning. !!!")
    return jsonify({"error": "File upload failed due to an unknown server error"}), 500

@app.route('/api/delete-file/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    user_id = session['user_id']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    
    if not file_id:
        return jsonify({"error": "File ID is required"}), 400

    try:
        file_to_delete = None
        for filename in os.listdir(user_folder):
            if filename.startswith(file_id):
                file_to_delete = filename
                break
        
        if file_to_delete:
            file_path = os.path.join(user_folder, file_to_delete)
            os.remove(file_path)
            return jsonify({"msg": f"File {file_to_delete} deleted successfully"}), 200
        else:
            return jsonify({"error": "File not found for this user"}), 404
    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({"error": "Failed to delete file on server"}), 500

# --- 自动清理任务 ---

def cleanup_expired_sessions():
    """定期清理过期的 session 文件和对应的用户上传文件"""
    SESSION_LIFETIME = 3600 # 60分钟 (3600秒)
    
    while True:
        # 1. 清理上传文件夹 (基于我们的自定义活动追踪)
        with session_lock:
            now = time.time()
            expired_user_ids = []
            for user_id, last_activity in session_activity.items():
                if now - last_activity > SESSION_LIFETIME:
                    expired_user_ids.append(user_id)
            
            for user_id in expired_user_ids:
                print(f"User activity for {user_id} expired. Cleaning up uploaded files...")
                user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
                if os.path.exists(user_folder):
                    shutil.rmtree(user_folder) # 删除整个文件夹
                del session_activity[user_id]
        
        # 2. 清理过期的孤儿 session 文件 (基于文件最后修改时间)
        try:
            session_dir = app.config['SESSION_FILE_DIR']
            now = time.time()
            for filename in os.listdir(session_dir):
                file_path = os.path.join(session_dir, filename)
                # os.path.getmtime(file_path) 获取文件的最后修改时间戳
                if os.path.isfile(file_path):
                    if now - os.path.getmtime(file_path) > SESSION_LIFETIME:
                        print(f"Orphan session file {filename} expired. Deleting...")
                        os.remove(file_path)
        except Exception as e:
            print(f"Error during orphan session file cleanup: {e}")

        # 每 5 分钟检查一次
        time.sleep(300)

def find_file_by_id(user_folder, file_id):
    """在一个用户的文件夹中，根据 file_id (不带扩展名) 查找完整的文件名"""
    if not os.path.exists(user_folder):
        return None
    for filename in os.listdir(user_folder):
        if filename.startswith(file_id):
            return os.path.join(user_folder, filename)
    return None

@app.route('/api/file-info/<file_id>', methods=['GET'])
def get_file_info(file_id):
    """使用 ffprobe 获取文件的详细元数据"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User session not found"}), 401

    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    file_path = find_file_by_id(user_folder, file_id)

    if not file_path:
        return jsonify({"error": "File not found"}), 404

    try:
        # 使用 ffprobe 命令获取 JSON 格式的输出
        command = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        
        # 执行命令
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # 解析 JSON 输出
        metadata = json.loads(result.stdout)
        
        return jsonify(metadata)

    except FileNotFoundError:
        print("!!! ERROR: 'ffprobe' command not found. Make sure FFmpeg is installed and in your system's PATH. !!!")
        return jsonify({"error": "Server configuration error: ffprobe is not installed or not in PATH."}), 500
    except subprocess.CalledProcessError as e:
        # 如果 ffprobe 返回非零退出码 (例如，文件损坏)
        print(f"!!! ERROR: ffprobe failed for file {file_path}. Error: {e.stderr} !!!")
        return jsonify({"error": "Failed to probe file. It might be corrupted.", "details": e.stderr}), 500
    except Exception as e:
        print(f"!!! An unexpected error occurred while probing file: {e} !!!")
        return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR']) # 确保 session 文件夹存在
    cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
    cleanup_thread.start()
    app.run(debug=True)