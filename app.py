from flask import Flask, Response, request,render_template_string
from dotenv import load_dotenv
import cv2
import threading

# Tải các biến môi trường từ tệp .env

app = Flask(__name__)


# Đối tượng camera global để quản lý tài nguyên camera
camera_instances = {}
camera_locks = {}  # Đối tượng khóa để đồng bộ hóa truy cập camera

def generate_frames(camera_index):
    if camera_index not in camera_instances:
        camera_locks[camera_index] = threading.Lock()
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"Error: Unable to open camera {camera_index}")
            return
        camera_instances[camera_index] = cap

    with camera_locks[camera_index]:
        cap = camera_instances[camera_index]

        while True:
            success, frame = cap.read()
            if not success:
                break
            frame = cv2.resize(frame, (480, 320))
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # Yield frame in the format of a multipart HTTP response
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        cap.release()
        del camera_instances[camera_index]
        del camera_locks[camera_index]  # Xóa khóa khi không còn sử dụng

@app.route('/video_feed/<int:camera_index>')
def video_feed(camera_index):
    return Response(generate_frames(camera_index),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed/')
def video_feed_list():
    # Tạo HTML cho iframe
    html = '<h2>chưa thiết lập camera</h2>'
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
