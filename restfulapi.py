from flask import Flask, request, send_from_directory, jsonify, abort
import os

app = Flask(__name__)
BASE_DIR = "datasets"
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  
# List files
@app.route('/datasets/<category>', methods=['GET'])
def list_files(category):
    dir_path = os.path.join(BASE_DIR, category)
    if not os.path.isdir(dir_path):
        abort(404, description="Category not found.")
    return jsonify({"files": os.listdir(dir_path)})

# Download file
@app.route('/datasets/<category>/<filename>', methods=['GET'])
def download_file(category, filename):
    dir_path = os.path.join(BASE_DIR, category)
    if not os.path.isfile(os.path.join(dir_path, filename)):
        abort(404, description="File not found.")
    return send_from_directory(directory=dir_path, path=filename, as_attachment=True)

# Upload or update a file
@app.route('/datasets/<category>', methods=['POST'])
def upload_file(category):
    if 'file' not in request.files:
        abort(400, description="No file part in the request.")
    file = request.files['file']
    if file.filename == '':
        abort(400, description="No selected file.")

    dir_path = os.path.join(BASE_DIR, category)
    os.makedirs(dir_path, exist_ok=True)

    file.save(os.path.join(dir_path, file.filename))
    return jsonify({"message": f"File '{file.filename}' uploaded successfully."})

# Delete a file
@app.route('/datasets/<category>/<filename>', methods=['DELETE'])
def delete_file(category, filename):
    file_path = os.path.join(BASE_DIR, category, filename)
    if not os.path.isfile(file_path):
        abort(404, description="File not found.")
    os.remove(file_path)
    return jsonify({"message": f"File '{filename}' deleted successfully."})

if __name__ == '__main__':
    app.run(debug=True)