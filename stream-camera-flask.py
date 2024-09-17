from flask import Flask, Response, render_template_string
import cv2
import threading
import time

app = Flask(__name__)

# Đối tượng camera global để quản lý tài nguyên camera
output_frames = {}  # Lưu frame cuối cùng đã đọc từ camera
frame_threads = {}  # Threads cho mỗi camera

def capture_camera(camera_index):
    """Chức năng này sẽ đọc frame từ camera và lưu trữ nó để chuyển tiếp."""
    global output_frames
    cap = cv2.VideoCapture(camera_index)
    
    # Đặt độ phân giải và FPS của camera
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)  # Chiều rộng Full HD
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080) # Chiều cao Full HD
    cap.set(cv2.CAP_PROP_FPS, 45)
    
    if not cap.isOpened():
        print(f"Error: Unable to open camera {camera_index}")
        return
    
    while True:
        success, frame = cap.read()
        if not success:
            print(f"Warning: Unable to read frame from camera {camera_index}")
            time.sleep(0.1)  # Tạm dừng ngắn để tránh quá tải CPU khi camera không hoạt động
            continue
        
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
        output_frames[camera_index] = buffer.tobytes()
        time.sleep(0.01)  # Điều chỉnh tốc độ đọc frame để tránh quá tải CPU
    
    cap.release()

def generate_frames(camera_index):
    """Chuyển tiếp các frame từ buffer tới client."""
    while True:
        frame = output_frames.get(camera_index)
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # Nếu chưa có frame nào, chờ đợi
            time.sleep(0.1)

@app.route('/video_feed/<int:camera_index>')
def video_feed(camera_index):
    global frame_threads
    if camera_index not in output_frames:
        output_frames[camera_index] = None
    
    # Nếu thread đọc frame từ camera chưa chạy, khởi động nó
    if camera_index not in frame_threads or not frame_threads[camera_index].is_alive():
        frame_threads[camera_index] = threading.Thread(target=capture_camera, args=(camera_index,))
        print(f"Starting thread for camera {camera_index}")
        frame_threads[camera_index].start()

    # Chuyển tiếp luồng video tới client
    return Response(generate_frames(camera_index),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed/')
def video_feed_():
    html = '''
    <p>chưa thiết lập camera</p>
    
    '''
    return render_template_string(html)

@app.route('/')
def index():
    html = '''
    <p>Hello, world!</p>
    
    '''
    return render_template_string(html)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8543, debug=True)
