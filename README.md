# 文件下载二维码服务

这是一个基于 Flask 的文件上传服务。用户上传文件后，页面会直接生成该文件的下载二维码，适合部署到云服务器或带公网域名的主机上使用。

## 功能

- 上传文件并生成下载二维码
- 自动生成可对外访问的下载链接
- 兼容反向代理场景下的域名和 HTTPS
- 自动清理 24 小时前上传的文件

## 环境要求

- Windows、macOS 或 Linux
- Python 3.10 及以上

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 直接启动

应用默认使用 Waitress 作为本地或内网 WSGI 服务，不再使用 Flask 调试服务器。

```bash
python app.py
```

默认监听：

```text
127.0.0.1:8000
```

浏览器访问：

```text
http://127.0.0.1:8000
```

## 环境变量

- `APP_HOST`：监听地址，默认 `0.0.0.0`
- `APP_PORT`：监听端口，默认 `8000`
- `PUBLIC_BASE_URL`：可选，固定生成二维码时使用的公网地址，例如 `https://files.example.com`

示例：

```bash
APP_HOST=0.0.0.0 APP_PORT=8080 PUBLIC_BASE_URL=https://files.example.com python app.py
```

在 Windows PowerShell 中：

```powershell
$env:APP_HOST = "0.0.0.0"
$env:APP_PORT = "8080"
$env:PUBLIC_BASE_URL = "https://files.example.com"
python app.py
```

## 部署方式

### 方式一：服务器直接暴露端口

仅适合临时内网测试，不作为当前推荐的公网部署方式。

1. 把项目部署到服务器。
2. 安装依赖。
3. 放行应用端口，例如 `8000` 或 `8080`。
4. 启动 `python app.py`。
5. 通过 `http://公网IP:端口` 访问。

### 方式二：Nginx 或其他反向代理

应用已经启用代理头处理，放在 Nginx、Caddy 或 Apache 后面时，可以自动识别外部域名和 HTTPS 协议。

推荐做法：

1. 应用只监听本机端口，例如 `127.0.0.1:8000`。
2. Nginx 对外监听 `80` 和 `443`。
3. `80` 统一跳转到 `https://你的域名`。
4. `443` 反向代理到 `http://127.0.0.1:8000`。
5. 固定二维码域名时，设置 `PUBLIC_BASE_URL=https://你的域名`。
6. 将 `nginx.ssdwm.conf` 放到 Nginx 站点配置目录后重新加载 Nginx。

示例 Nginx 配置见项目中的 `nginx.ssdwm.conf`。

## 使用方法

1. 打开首页。
2. 选择文件并上传。
3. 页面会自动生成下载二维码和下载链接。
4. 手机扫码后即可直接访问下载地址。

## 注意事项

- 如果使用云服务器，需要在安全组或防火墙中放行 `80` 和 `443`，不建议继续对公网暴露 `8000`。
- 某些文件类型在微信内可能先预览或提示跳转浏览器，这是微信自身行为。
- 上传文件保存在 `uploads` 目录下，并会在 24 小时后自动清理。
- 当前文件保存在本地磁盘，适合轻量部署；如果后续需要多机部署或对象存储，可以再改成 OSS、COS 或 S3。