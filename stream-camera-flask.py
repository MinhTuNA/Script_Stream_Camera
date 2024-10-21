from flask import Flask, Response, render_template_string
import cv2
import threading
import time
import requests
import socket
import random

app = Flask(__name__)

INSTANCE_PORT = random.randint(8562, 65535)


def get_local_ip():
    """Lấy địa chỉ IP mạng cục bộ, loại trừ localhost"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # Google DNS, chỉ để xác định IP cục bộ
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def send_ip_port_on_startup():
    # Lấy IP cục bộ chính xác
    server_ip = get_local_ip()
    print(f"Server IP: {server_ip}, Port: {INSTANCE_PORT}")
    # Headers và API URL
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0YWJsZU5hbWUiOiJI4bqhdCDEkWnhu4F1fn4yIiwiaWF0IjoxNzI5MjQ2NzE5LCJleHAiOjMzMjU1Mjg5MTE5fQ.jUUk-Cu5INZfXah7in-L1PMt9_IG_5xoCogbJaG49Uc",
    }
    api_url = "http://117.3.0.23:8543/api/auth-db/ip_port/script"
    data = {"ip_port": f"{server_ip}:{INSTANCE_PORT}"}
    try:
        response = requests.post(api_url, headers=headers, json=data)
        print(f"API response: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to API: {e}")


send_ip_port_on_startup()


output_frames = {}  # Lưu frame cuối cùng đã đọc từ camera
frame_threads = {}  # Threads cho mỗi camera
resolution_map = {
    "360": (640, 360),  # 360p
    "480": (854, 480),  # 480p
    "720": (1280, 720),  # 720p
    "1080": (1920, 1080),  # 1080p
}


def capture_camera(camera_index):
    """Chức năng này sẽ đọc frame từ camera và lưu trữ nó để chuyển tiếp."""
    global output_frames
    cap = cv2.VideoCapture(camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1280)
    if not cap.isOpened():
        print(f"Error: Unable to open camera {camera_index}")
        return

    while True:
        success, frame = cap.read()
        if not success:
            print(f"Warning: Unable to read frame from camera {camera_index}")
            time.sleep(0.1)
            continue

        # Lưu frame gốc để mã hóa
        output_frames[camera_index] = frame  # Lưu frame chưa thay đổi kích thước

        time.sleep(0.01)  # Điều chỉnh tốc độ đọc frame để tránh quá tải CPU

    cap.release()


def generate_frames(camera_index, quality):
    """Chuyển tiếp các frame từ buffer tới client với kích thước đã thay đổi."""
    while True:
        frame = output_frames.get(camera_index)
        if frame is not None:
            # Thay đổi kích thước khung hình
            resolution = resolution_map.get(
                quality, resolution_map["720"]
            )  # Mặc định là 720p
            resized_frame = cv2.resize(
                frame, resolution
            )  # Thay đổi kích thước khung hình

            # Mã hóa frame đã thay đổi kích thước thành JPEG
            _, buffer = cv2.imencode(
                ".jpg", resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 100]
            )
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
        else:
            time.sleep(0.1)


@app.route("/video_feed/<int:camera_index>/<quality>")
def video_feed(camera_index, quality):
    if camera_index not in output_frames:
        output_frames[camera_index] = None

    if camera_index not in frame_threads or not frame_threads[camera_index].is_alive():
        frame_threads[camera_index] = threading.Thread(
            target=capture_camera, args=(camera_index,)
        )
        print(f"Starting thread for camera {camera_index}")
        frame_threads[camera_index].start()

    # Chuyển tiếp luồng video tới client
    return Response(
        generate_frames(camera_index, quality),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/")
def index():
    html = """
    <h1>Webcam Stream</h1>
    <p>Để xem video, hãy sử dụng định dạng sau:</p>
    <p><code>http://<your_ip>:8543/video_feed/<camera_index>/<quality></code></p>
    <p>Ví dụ: <code>http://<your_ip>:8543/video_feed/0/720</code></p>
    <p>Các độ phân giải có sẵn:</p>
    <ul>
        <li>360p: 360</li>
        <li>480p: 480</li>
        <li>720p: 720</li>
        <li>1080p: 1080</li>
    </ul>
    """
    return render_template_string(html)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=INSTANCE_PORT, debug=False)
