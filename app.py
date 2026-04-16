from __future__ import annotations

import base64
import io
import mimetypes
import secrets
import shutil
import socket
import time
from pathlib import Path

import qrcode
from flask import Flask, abort, redirect, render_template_string, request, send_file, url_for
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_AGE_SECONDS = 24 * 60 * 60
MAX_CONTENT_LENGTH = 1024 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


HTML_TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>文件下载二维码</title>
    <style>
        :root {
            color-scheme: light;
            --bg: #f7f1e8;
            --panel: #fffaf2;
            --panel-border: #d6c8b5;
            --text: #2d241b;
            --muted: #6f6559;
            --accent: #146c43;
            --accent-hover: #0f5535;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            min-height: 100vh;
            font-family: "Microsoft YaHei", sans-serif;
            color: var(--text);
            background:
                radial-gradient(circle at top left, rgba(20, 108, 67, 0.16), transparent 32%),
                radial-gradient(circle at right bottom, rgba(185, 142, 73, 0.18), transparent 28%),
                var(--bg);
            display: grid;
            place-items: center;
            padding: 24px;
        }

        main {
            width: min(960px, 100%);
            background: rgba(255, 250, 242, 0.94);
            border: 1px solid var(--panel-border);
            border-radius: 24px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            overflow: hidden;
            box-shadow: 0 20px 60px rgba(66, 45, 17, 0.12);
        }

        section {
            padding: 32px;
        }

        .intro {
            background: linear-gradient(160deg, rgba(20, 108, 67, 0.1), rgba(255, 250, 242, 0));
            border-right: 1px solid var(--panel-border);
        }

        h1 {
            margin: 0 0 12px;
            font-size: clamp(28px, 4vw, 40px);
            line-height: 1.1;
        }

        p {
            margin: 0 0 14px;
            line-height: 1.7;
            color: var(--muted);
        }

        .pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            border-radius: 999px;
            padding: 8px 12px;
            background: rgba(20, 108, 67, 0.09);
            color: var(--accent);
            font-size: 14px;
            margin-bottom: 18px;
        }

        form {
            display: grid;
            gap: 16px;
        }

        .field {
            display: grid;
            gap: 8px;
        }

        label {
            font-weight: 600;
        }

        input[type="file"],
        input[type="text"] {
            width: 100%;
            padding: 12px 14px;
            border-radius: 14px;
            border: 1px solid var(--panel-border);
            background: white;
            color: var(--text);
        }

        button {
            border: 0;
            border-radius: 14px;
            padding: 14px 18px;
            background: var(--accent);
            color: white;
            font-weight: 700;
            cursor: pointer;
            transition: background 0.2s ease;
        }

        button:hover {
            background: var(--accent-hover);
        }

        .result {
            display: grid;
            place-items: center;
            gap: 12px;
            text-align: center;
        }

        .result img {
            width: min(320px, 100%);
            aspect-ratio: 1;
            border-radius: 20px;
            padding: 16px;
            background: white;
            border: 1px solid var(--panel-border);
        }

        .result a {
            color: var(--accent);
            word-break: break-all;
        }

        .warning {
            margin-top: 8px;
            color: #8e4d17;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <main>
        <section class="intro">
            <div class="pill">微信扫码后可直接访问下载链接</div>
            <h1>上传文件并生成下载二维码</h1>
            <p>在电脑上选择文件上传，服务会为该文件生成一个可访问的下载地址和二维码。</p>
            <p>手机和电脑需要在同一网络下，并且地址栏中的主机名需要替换为电脑的局域网 IP。</p>
            <p>为避免文件长期堆积，服务会自动清理 24 小时前上传的文件。</p>
        </section>
        <section>
            {% if qr_image %}
            <div class="result">
                <img src="data:image/png;base64,{{ qr_image }}" alt="文件下载二维码">
                <strong>{{ file_name }}</strong>
                <a href="{{ download_url }}" target="_blank">{{ download_url }}</a>
                <p class="warning">如果微信里无法直接保存某些文件类型，可点击链接后在系统浏览器中继续下载。</p>
                <a href="{{ url_for('index') }}">继续上传其他文件</a>
            </div>
            {% else %}
            <form method="post" enctype="multipart/form-data">
                <div class="field">
                    <label for="server_base_url">服务器访问地址</label>
                    <input id="server_base_url" name="server_base_url" type="text" value="{{ default_base_url }}" placeholder="例如 http://192.168.1.10:5500" required>
                </div>
                <div class="field">
                    <label for="file">选择文件</label>
                    <input id="file" name="file" type="file" required>
                </div>
                <button type="submit">上传并生成二维码</button>
            </form>
            {% endif %}
        </section>
    </main>
</body>
</html>
"""


def guess_local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def cleanup_old_uploads() -> None:
    now = time.time()
    for directory in UPLOAD_DIR.iterdir():
        if not directory.is_dir():
            continue
        if now - directory.stat().st_mtime > MAX_FILE_AGE_SECONDS:
            shutil.rmtree(directory, ignore_errors=True)


def build_qr_code(content: str) -> str:
    image = qrcode.make(content)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def get_saved_file(token: str) -> tuple[Path, str]:
    folder = UPLOAD_DIR / token
    if not folder.is_dir():
        abort(404)

    for item in folder.iterdir():
        if item.is_file():
            return item, item.name
    abort(404)


@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_old_uploads()
    default_base_url = f"http://{guess_local_ip()}:5500"

    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE, qr_image=None, default_base_url=default_base_url)

    uploaded_file = request.files.get("file")
    base_url = (request.form.get("server_base_url") or "").strip().rstrip("/")
    if not uploaded_file or not uploaded_file.filename:
        abort(400, "请先选择文件")
    if not base_url:
        abort(400, "请输入服务器访问地址")

    file_name = secure_filename(uploaded_file.filename)
    if not file_name:
        abort(400, "文件名无效")

    token = secrets.token_urlsafe(8)
    folder = UPLOAD_DIR / token
    folder.mkdir(parents=True, exist_ok=False)
    saved_path = folder / file_name
    uploaded_file.save(saved_path)

    download_url = f"{base_url}{url_for('download_file', token=token)}"
    qr_image = build_qr_code(download_url)
    return render_template_string(
        HTML_TEMPLATE,
        qr_image=qr_image,
        file_name=file_name,
        download_url=download_url,
        default_base_url=default_base_url,
    )


@app.route("/download/<token>")
def download_file(token: str):
    saved_path, download_name = get_saved_file(token)
    mime_type, _ = mimetypes.guess_type(saved_path.name)
    return send_file(saved_path, as_attachment=True, download_name=download_name, mimetype=mime_type)


@app.route("/favicon.ico")
def favicon():
    return redirect("data:,", code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500, debug=True)