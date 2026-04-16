from __future__ import annotations

import base64
import io
import mimetypes
import os
import secrets
import socket
from pathlib import Path

import qrcode
from flask import Flask, abort, redirect, render_template_string, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_CONTENT_LENGTH = 1024 * 1024 * 1024
DEFAULT_HOST = os.getenv("APP_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("APP_PORT", "8000"))
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)


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
            <h1>先生成二维码，再上传文件</h1>
            <p>先创建一个固定下载地址和二维码，再把文件上传到这个二维码对应的槽位中。</p>
            <p>每个二维码只能绑定一个文件，文件上传后不会被程序自动删除。</p>
            <p>部署到服务器后，页面会自动使用当前域名生成下载链接；如有独立公网域名，也可通过环境变量固定访问地址。</p>
        </section>
        <section>
            {% if token %}
            <div class="result">
                <img src="data:image/png;base64,{{ qr_image }}" alt="文件下载二维码">
                <strong>{% if file_name %}{{ file_name }}{% else %}二维码已生成，等待上传文件{% endif %}</strong>
                <a href="{{ download_url }}" target="_blank">{{ download_url }}</a>
                {% if file_uploaded %}
                <p class="warning">如果微信里无法直接保存某些文件类型，可点击链接后在系统浏览器中继续下载。</p>
                {% else %}
                <p class="warning">二维码已经固定。现在上传文件后，这个链接就会开始提供下载。</p>
                {% endif %}
            </div>
            {% if not file_uploaded %}
            <form method="post" enctype="multipart/form-data" action="{{ url_for('upload_for_token', token=token) }}">
                <div class="field">
                    <label for="file">选择文件</label>
                    <input id="file" name="file" type="file" required>
                </div>
                <button type="submit">上传到当前二维码</button>
            </form>
            {% else %}
            <div class="result">
                <a href="{{ url_for('index') }}">继续上传其他文件</a>
            </div>
            {% endif %}
            {% else %}
            <form method="post" action="{{ url_for('create_qr') }}">
                <button type="submit">生成二维码</button>
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


def build_qr_code(content: str) -> str:
    image = qrcode.make(content)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def get_public_base_url() -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    return request.host_url.rstrip("/")


def get_saved_file(token: str) -> tuple[Path, str]:
    folder = UPLOAD_DIR / token
    if not folder.is_dir():
        abort(404)

    for item in folder.iterdir():
        if item.is_file():
            return item, item.name
    abort(404)


def find_existing_file(token: str) -> Path | None:
    folder = UPLOAD_DIR / token
    if not folder.is_dir():
        return None

    for item in folder.iterdir():
        if item.is_file():
            return item
    return None


def render_index(*, token: str | None = None, file_name: str | None = None):
    default_base_url = PUBLIC_BASE_URL or f"http://{guess_local_ip()}:{DEFAULT_PORT}"
    download_url = None
    qr_image = None
    file_uploaded = bool(file_name)

    if token:
        download_url = f"{get_public_base_url()}{url_for('download_file', token=token)}"
        qr_image = build_qr_code(download_url)

    return render_template_string(
        HTML_TEMPLATE,
        token=token,
        file_name=file_name,
        file_uploaded=file_uploaded,
        download_url=download_url,
        qr_image=qr_image,
        default_base_url=default_base_url,
    )


@app.route("/", methods=["GET"])
def index():
    return render_index()


@app.route("/create", methods=["POST"])
def create_qr():
    token = secrets.token_urlsafe(8)
    folder = UPLOAD_DIR / token
    folder.mkdir(parents=True, exist_ok=False)
    return render_index(token=token)


@app.route("/upload/<token>", methods=["POST"])
def upload_for_token(token: str):
    folder = UPLOAD_DIR / token
    if not folder.is_dir():
        abort(404, "二维码不存在，请重新生成")

    existing_file = find_existing_file(token)
    if existing_file is not None:
        abort(409, "该二维码已绑定文件，不能重复上传")

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        abort(400, "请先选择文件")

    file_name = secure_filename(uploaded_file.filename)
    if not file_name:
        abort(400, "文件名无效")

    saved_path = folder / file_name
    uploaded_file.save(saved_path)
    return render_index(token=token, file_name=file_name)


@app.route("/download/<token>")
def download_file(token: str):
    try:
        saved_path, download_name = get_saved_file(token)
    except Exception:
        if (UPLOAD_DIR / token).is_dir():
            return "该二维码对应的文件还未上传，请稍后再试。", 404
        raise
    mime_type, _ = mimetypes.guess_type(saved_path.name)
    return send_file(saved_path, as_attachment=True, download_name=download_name, mimetype=mime_type)


@app.route("/favicon.ico")
def favicon():
    return redirect("data:,", code=302)


if __name__ == "__main__":
    from waitress import serve

    print(f"Server is running at http://127.0.0.1:{DEFAULT_PORT} (listening on {DEFAULT_HOST}:{DEFAULT_PORT})", flush=True)
    serve(app, host=DEFAULT_HOST, port=DEFAULT_PORT)