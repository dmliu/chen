import subprocess
import sys
import os

def main():
    # 检查uwsgi是否已安装
    try:
        import uwsgi  # noqa: F401
        has_uwsgi = True
    except ImportError:
        has_uwsgi = False

    if not has_uwsgi:
        print("未检测到uwsgi，正在尝试自动安装...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uwsgi"])

    # 启动uwsgi
    ini_path = os.path.join(os.path.dirname(__file__), "uwsgi.ini")
    print(f"正在使用uwsgi启动服务，配置文件: {ini_path}", flush=True)
    subprocess.run([sys.executable, "-m", "uwsgi", "--ini", ini_path])

if __name__ == "__main__":
    main()