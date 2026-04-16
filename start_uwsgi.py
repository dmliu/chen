import os
import shutil
import subprocess
import sys

def main():
    uwsgi_command = shutil.which("uwsgi")
    if uwsgi_command is None:
        print("未检测到uwsgi，正在尝试自动安装...", flush=True)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "uwsgi"])
        uwsgi_command = shutil.which("uwsgi")
        if uwsgi_command is None:
            raise RuntimeError("uwsgi 安装完成，但未找到 uwsgi 可执行文件")

    ini_path = os.path.join(os.path.dirname(__file__), "uwsgi.ini")
    print(f"正在使用uwsgi启动服务，配置文件: {ini_path}", flush=True)
    subprocess.run([uwsgi_command, "--ini", ini_path], check=True)

if __name__ == "__main__":
    main()