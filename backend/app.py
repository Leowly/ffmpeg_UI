import os
import uuid
import shutil
import time
import threading
import json
import subprocess
import re
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_session import Session
from werkzeug.utils import secure_filename

# 初始化 Flask 应用
app = Flask(__name__)

# --- 核心配置修改 ---
app.config['SECRET_KEY'] = 'a-super-secret-key-for-my-ffmpeg-project'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flask_sessions')
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
Session(app)

# 配置 CORS
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "http://localhost:5173"}})

# 配置文件夹
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'outputs') # 新增：输出文件夹
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER


# --- 任务管理 (新增) ---
tasks = {}
tasks_lock = threading.Lock()
# ---------------------

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
    user_id = session['user_id']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    if not os.path.exists(user_folder):
        return jsonify([])
    files_info = []
    for filename in os.listdir(user_folder):
        file_path = os.path.join(user_folder, filename)
        files_info.append({
            "uid": filename, "id": filename, "name": filename, "status": "done",
            "size": os.path.getsize(file_path),
            "response": {"file_id": filename, "original_name": filename, "temp_path": file_path}
        })
    return jsonify(files_info)

def find_unique_filename(folder, filename):
    base, extension = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    save_path = os.path.join(folder, unique_filename)
    while os.path.exists(save_path):
        unique_filename = f"{base} ({counter}){extension}"
        save_path = os.path.join(folder, unique_filename)
        counter += 1
    return unique_filename, save_path

@app.route('/api/upload', methods=['POST'])
def upload_file():
    user_id = session['user_id']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    if not os.path.exists(user_folder):
        os.makedirs(user_folder)
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file:
        original_filename = secure_filename(file.filename)
        unique_filename, save_path = find_unique_filename(user_folder, original_filename)
        try:
            file.save(save_path)
            file_id = unique_filename
            response_data = {
                "msg": "Upload successful", "file_id": file_id, "original_name": file_id, "temp_path": save_path
            }
            return jsonify(response_data), 200
        except Exception as e:
            return jsonify({"error": f"Server error: failed to save file. Exception: {e}"}), 500
    return jsonify({"error": "File upload failed due to an unknown server error"}), 500

@app.route('/api/delete-file', methods=['DELETE'])
def delete_file():
    file_id = request.args.get('filename')
    user_id = session['user_id']
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    if not file_id:
        return jsonify({"error": "Filename parameter is required"}), 400
    if os.path.basename(file_id) != file_id:
        return jsonify({"error": "Invalid filename format (path traversal detected)"}), 400
    try:
        file_path = os.path.join(user_folder, file_id)
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({"msg": f"File '{file_id}' deleted successfully"}), 200
        else:
            return jsonify({"error": "File not found for this user"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to delete file on server"}), 500

@app.route('/api/file-info', methods=['GET'])
def get_file_info():
    file_id = request.args.get('filename')
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "User session not found"}), 401
    if not file_id:
        return jsonify({"error": "Filename parameter is required"}), 400
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    if os.path.basename(file_id) != file_id:
        return jsonify({"error": "Invalid filename format (path traversal detected)"}), 400
    file_path = os.path.join(user_folder, file_id)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    try:
        command = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', file_path]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        metadata = json.loads(result.stdout)
        return jsonify(metadata)
    except FileNotFoundError:
        return jsonify({"error": "Server configuration error: ffprobe is not installed or not in PATH."}), 500
    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Failed to probe file. It might be corrupted.", "details": e.stderr}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected server error occurred: {e}"}), 500


# --- FFmpeg Processing Logic (新增) ---
def run_ffmpeg_task(task_id, command, output_path, total_duration):
    """在后台线程中运行 FFmpeg 命令并更新任务状态"""
    try:
        process = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   universal_newlines=True, encoding="utf-8")
        
        # 正则表达式用于从 ffmpeg 输出中解析时间
        duration_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

        for line in iter(process.stderr.readline, ''):
            match = duration_regex.search(line)
            if match:
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = int(match.group(3))
                ms = int(match.group(4))
                current_time = hours * 3600 + minutes * 60 + seconds + ms / 100.0
                
                if total_duration > 0:
                    progress = min(100, int((current_time / total_duration) * 100))
                    with tasks_lock:
                        if task_id in tasks:
                            tasks[task_id]['progress'] = progress

        process.wait()

        with tasks_lock:
            if process.returncode == 0:
                tasks[task_id].update({"status": "completed", "progress": 100, "output_path": output_path})
            else:
                stderr_output = process.stderr.read()
                tasks[task_id].update({"status": "failed", "error": f"FFmpeg failed with code {process.returncode}. Error: {stderr_output}"})

    except Exception as e:
        with tasks_lock:
            tasks[task_id].update({"status": "failed", "error": str(e)})


@app.route('/api/process', methods=['POST'])
def process_file():
    user_id = session['user_id']
    user_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], user_id)
    user_output_folder = os.path.join(app.config['OUTPUT_FOLDER'], user_id)
    
    if not os.path.exists(user_output_folder):
        os.makedirs(user_output_folder)

    data = request.json
    
    # --- 关键改动 1: 从 'files' 字段获取文件ID列表 ---
    file_ids = data.get('files', [])
    if not file_ids:
        return jsonify({"error": "No files selected for processing"}), 400

    created_tasks = []

    # --- 关键改动 2: 循环处理每个文件，并为每个文件创建任务 ---
    for file_id in file_ids:
        input_path = os.path.join(user_upload_folder, file_id)
        if not os.path.exists(input_path):
            print(f"Skipping non-existent file: {file_id}")
            continue # 如果文件不存在，则跳过

        base, _ = os.path.splitext(file_id)
        # 为输出文件名添加一个唯一后缀，防止重名
        output_suffix = f"processed_{str(uuid.uuid4())[:4]}"
        output_filename = f"{base}_{output_suffix}.{data['container']}"
        output_path = os.path.join(user_output_folder, output_filename)

        command = ['ffmpeg', '-y', '-i', input_path]
        
        # 裁剪 (所有文件应用相同的裁剪设置)
        if 'startTime' in data and 'endTime' in data:
            command.extend(['-ss', str(data['startTime']), '-to', str(data['endTime'])])

        # 视频处理
        is_video_container = data['container'] in ['mp4', 'mkv', 'mov']
        if is_video_container:
            if data['videoCodec'] == 'copy':
                command.extend(['-c:v', 'copy'])
            else:
                command.extend(['-c:v', data['videoCodec']])
                # 智能判断是否添加比特率和分辨率参数
                if 'videoBitrate' in data:
                     command.extend(['-b:v', f"{data['videoBitrate']}k"])
                if 'resolution' in data:
                     command.extend(['-s', f"{data['resolution']['width']}x{data['resolution']['height']}"])
        else:
            command.append('-vn')

        # 音频处理
        if data['audioCodec'] == 'copy':
            command.extend(['-c:a', 'copy'])
        else:
            command.extend(['-c:a', data['audioCodec']])
            # 智能判断是否添加音频比特率参数
            if 'audioBitrate' in data:
                 command.extend(['-b:a', f"{data['audioBitrate']}k"])

        command.append(output_path)

        # 为当前文件创建并启动任务
        task_id = str(uuid.uuid4())
        with tasks_lock:
            tasks[task_id] = {
                "status": "processing", 
                "progress": 0,
                "command": " ".join(command) # 存储命令用于调试
            }

        total_duration = data.get('totalDuration', 0)
        
        thread = threading.Thread(target=run_ffmpeg_task, args=(task_id, command, output_path, total_duration))
        thread.daemon = True
        thread.start()
        
        created_tasks.append({"file_id": file_id, "task_id": task_id})

    # --- 关键改动 3: 返回所有已创建任务的信息 ---
    return jsonify({"msg": f"Successfully created {len(created_tasks)} tasks.", "tasks": created_tasks}), 202


@app.route('/api/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    with tasks_lock:
        task = tasks.get(task_id)
        if task:
            return jsonify(task)
        else:
            return jsonify({"error": "Task not found"}), 404
# -------------------------------------


# --- 自动清理任务 ---
def cleanup_expired_sessions():
    """定期清理过期的 session 文件和对应的用户上传文件"""
    SESSION_LIFETIME = 3600 # 60分钟
    while True:
        # 清理上传文件夹
        with session_lock:
            now = time.time()
            expired_user_ids = [uid for uid, t in session_activity.items() if now - t > SESSION_LIFETIME]
            for user_id in expired_user_ids:
                print(f"User activity for {user_id} expired. Cleaning up files...")
                for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
                    user_folder = os.path.join(folder, user_id)
                    if os.path.exists(user_folder):
                        shutil.rmtree(user_folder)
                del session_activity[user_id]
        # 清理孤儿 session 文件
        try:
            session_dir = app.config['SESSION_FILE_DIR']
            now = time.time()
            for filename in os.listdir(session_dir):
                file_path = os.path.join(session_dir, filename)
                if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > SESSION_LIFETIME:
                    os.remove(file_path)
        except Exception as e:
            print(f"Error during orphan session file cleanup: {e}")
        time.sleep(300)

if __name__ == '__main__':
    if not os.path.exists(app.config['SESSION_FILE_DIR']):
        os.makedirs(app.config['SESSION_FILE_DIR'])
    cleanup_thread = threading.Thread(target=cleanup_expired_sessions, daemon=True)
    cleanup_thread.start()
    app.run(debug=True, threaded=True) # 确保 Flask 在多线程模式下运行