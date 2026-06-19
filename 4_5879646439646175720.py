import socketio
import eventlet
import numpy as np
from flask import Flask
import base64
from io import BytesIO
from PIL import Image
import cv2
import tflite_runtime.interpreter as tflite
import time

# SocketIO setup
sio = socketio.Server(cors_allowed_origins='*')
app = Flask(__name__)
speed_limit = 10

def img_preprocess(img):
    img = img[60:135, :, :]
    img = cv2.cvtColor(img, cv2.COLOR_RGB2YUV)
    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = cv2.resize(img, (200, 66))
    img = img / 255
    return img

# متغيرات لحساب متوسط FPS
fps_list = []
frame_count = 0
fps_avg_window = 50  # كل 50 frame

@sio.on('telemetry')
def telemetry(sid, data):
    global fps_list, frame_count

    speed = float(data['speed'])
    image = Image.open(BytesIO(base64.b64decode(data['image'])))
    image = np.asarray(image)
    image = img_preprocess(image)
    image = np.array([image], dtype=np.float32)

    start_time = time.time()

    # TFLite inference
    interpreter.set_tensor(input_details[0]['index'], image)
    interpreter.invoke()
    steering_angle = float(interpreter.get_tensor(output_details[0]['index']))

    end_time = time.time()
    fps = 1.0 / (end_time - start_time)

    # تحديث القائمة وعدد الفريمات
    fps_list.append(fps)
    frame_count += 1

    # حساب المتوسط كل 50 frame
    if frame_count % fps_avg_window == 0:
        avg_fps = sum(fps_list[-fps_avg_window:]) / fps_avg_window
        print(f"🕒 Average FPS over last {fps_avg_window} frames: {avg_fps:.2f}")

    throttle = 1.0 - speed / speed_limit
    print(f'Steering: {steering_angle:.4f} Throttle: {throttle:.2f} Speed: {speed:.2f}')
    send_control(steering_angle, throttle)

@sio.on('connect')
def connect(sid, environ):
    print('Connected - SID:', sid)
    send_control(0, 0)

def send_control(steering_angle, throttle):
    sio.emit('steer', data={
        'steering_angle': str(steering_angle),
        'throttle': str(throttle)
    })
    print(f"Sent control - Steering: {steering_angle}, Throttle: {throttle}")

if __name__ == '__main__':
    # ==== Load TFLite model باستخدام tflite_runtime ====
    interpreter = tflite.Interpreter(model_path='Notebooks/model_float16.tflite')
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print("TFLite Model loaded successfully (Pi)!")
    print("Waiting for simulator/vehicle connection on port 4567...")

    app = socketio.Middleware(sio, app)
    eventlet.wsgi.server(eventlet.listen(('', 4567)), app)