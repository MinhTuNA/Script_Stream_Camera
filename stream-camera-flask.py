from flask import Flask, Response, render_template_string
import cv2
import threading
import time
import requests
import socket
import random

app = Flask(__name__)


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
    server_ip = get_local_ip()
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0YWJsZU5hbWUiOiJSYXR-fjIiLCJpYXQiOjE3Mjk1MDE3NDcsImV4cCI6MzMyNTU1NDQxNDd9.YKBs0-2bZxJxUvuBIK8XaEqDd6pcLVuumMzf-hqpl7k",
    }
    api_url = "http://117.3.0.23:8543/api/auth-db/camera_url/script"
    try:
        response = requests.get(api_url, headers=headers)
        if response.status_code == 200 and response.text:
            port = response.text.split(":")[1]
            print(f"Using port from database: {port}")
        else:
            port = random.randint(8562, 65535)
            print(f"No data found in database. Random port: {port}")
            data = {"url": f"{server_ip}:{port}"}
            try:
                post_response = requests.post(api_url, headers=headers, json=data)
                print(
                    f"API response on POST: {post_response.status_code} - {post_response.text}"
                )
            except requests.exceptions.RequestException as e:
                print(f"Error sending data to API: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error checking data in API: {e}")

    return port


output_frames = {}
frame_threads = {}
resolution_map = {
    "360": (640, 360),
    "480": (854, 480),
    "720": (1280, 720),
    "1080": (1920, 1080),
}


def capture_camera(camera_index):
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
        output_frames[camera_index] = frame

        time.sleep(0.01)

    cap.release()


def generate_frames(camera_index, quality):
    while True:
        frame = output_frames.get(camera_index)
        if frame is not None:
            resolution = resolution_map.get(quality, resolution_map["720"])
            resized_frame = cv2.resize(frame, resolution)
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
    return Response(
        generate_frames(camera_index, quality),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


@app.route("/")
def index():
    html = """
    Hello world!
    """
    return render_template_string(html)


if __name__ == "__main__":
    INSTANCE_PORT = send_ip_port_on_startup()
    app.run(host="0.0.0.0", port=INSTANCE_PORT, debug=False)
