import os
import uuid
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

# 1. 初始化 Flask 应用
app = Flask(__name__)
# 使用 Flask-CORS 允许所有来源的跨域请求
CORS(app)

# 2. 配置上传文件的存储位置
# 我们将在 backend 文件夹下创建一个名为 'uploads' 的子文件夹来存放文件
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 3. 创建文件上传的 API 接口
@app.route('/api/upload', methods=['POST'])
def upload_file():
    # 检查请求中是否包含 'file' 部分
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files['file']

    # 如果用户没有选择文件，浏览器可能会提交一个没有文件名的空部分
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        # 确保文件名是安全的，防止路径遍历等攻击
        original_filename = secure_filename(file.filename)
        
        # 生成一个唯一的
        # 文件名，防止重名覆盖
        file_extension = os.path.splitext(original_filename)[1]
        unique_id = str(uuid.uuid4())
        unique_filename = unique_id + file_extension
        
        # 构造文件的完整保存路径
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # 保存文件
        file.save(save_path)
        
        # 向前端返回一个成功的 JSON 响应
        # 这与你之前在前端模拟的响应结构保持一致
        response_data = {
            "msg": "Upload successful",
            "file_id": unique_id, # 使用 UUID 作为文件 ID
            "original_name": original_filename,
            "temp_path": save_path # 返回服务器上的存储路径
        }
        return jsonify(response_data), 200

    return jsonify({"error": "File upload failed"}), 500
# 4. 创建文件删除的 API 接口
@app.route('/api/delete-file/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    if not file_id:
        return jsonify({"error": "File ID is required"}), 400

    try:
        # 在 uploads 文件夹中查找匹配 file_id 的文件
        file_to_delete = None
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            if filename.startswith(file_id):
                file_to_delete = filename
                break
        
        if file_to_delete:
            # 构造文件的完整路径
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_to_delete)
            
            # 删除文件
            os.remove(file_path)
            
            return jsonify({"msg": f"File {file_to_delete} deleted successfully"}), 200
        else:
            return jsonify({"error": "File not found on server"}), 404

    except Exception as e:
        print(f"Error deleting file: {e}")
        return jsonify({"error": "Failed to delete file on server"}), 500
if __name__ == '__main__':
    # 默认运行在 http://127.0.0.1:5000
    app.run(debug=True)