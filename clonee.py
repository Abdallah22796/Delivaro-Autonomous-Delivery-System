=========================================================

DELIVARO AUTONOMOUS SYSTEM V3

GPS + IMU + CNN + YOLO + QR DELIVERY + RETURN HOME

=========================================================

import cv2import numpy as npimport subprocessimport serialimport timeimport mathimport smbus2import foliumimport webbrowserimport threadingimport sys

from tensorflow import lite as tflitefrom ultralytics import YOLO

from gpiozero import (DigitalOutputDevice,PWMOutputDevice,Servo,DistanceSensor)

from gpiozero.pins.lgpio import LGPIOFactoryfrom picamera2 import Picamera2import requests

=========================================================

GPIO FACTORY

=========================================================

factory = LGPIOFactory()

=========================================================

---------------- MOTOR SETUP ----------------------------

=========================================================

IN1 = DigitalOutputDevice(21, pin_factory=factory)IN2 = DigitalOutputDevice(20, pin_factory=factory)

IN3 = DigitalOutputDevice(6, pin_factory=factory)IN4 = DigitalOutputDevice(5, pin_factory=factory)

ENA = PWMOutputDevice(13, pin_factory=factory)ENB = PWMOutputDevice(12, pin_factory=factory)led_left  = DigitalOutputDevice(25, pin_factory=factory) # ?????? ?????? ??? ?? 16led_right = DigitalOutputDevice(1, pin_factory=factory) # ?????? ?????? ??? ?? 26front_light = DigitalOutputDevice(7, pin_factory=factory)

RIGHT_CORRECTION = 1.0LEFT_CORRECTION = 1.0

=========================================================

---------------- SERVO SETUP ----------------------------

=========================================================

SERVO_PIN = 23servo = Servo(SERVO_PIN,min_pulse_width=0.0005,max_pulse_width=0.0025)

time.sleep(1)servo.value = 0time.sleep(0.5)servo.detach()

=========================================================

-------- ULTRASONIC + AVOIDANCE SERVO -------------------

=========================================================

ULTRA_FACTORY = LGPIOFactory()

ultra_sensor = DistanceSensor(echo=26,trigger=24,pin_factory=ULTRA_FACTORY)

ultra_servo = Servo(27,min_pulse_width=0.0005,max_pulse_width=0.0025,pin_factory=ULTRA_FACTORY)

=========================================================

---------------- QR SETTINGS ----------------------------

=========================================================

ALLOWED_QR = ""AUTO_CLOSE_DELAY = 5

=========================================================

---------------- YOLO SETUP -----------------------------

=========================================================



model = YOLO('newYOLOv8_2.onnx', task='detect')

EMERGENCY_STOP = FalseCURRENT_SPEED = 0.7ULTRA_STOP = FalseOBSTACLE_NEAR = FalseAVOID_DIRECTION = "CENTER"ULTRA_ACTIVE = True

=========================================================

---------------- STOP -----------------------------------

=========================================================

def stop_car():

ENA.value = 0
ENB.value = 0

IN1.off()
IN2.off()

IN3.off()
IN4.off()
set_signals("STOP")

#Rtaffic lightdef set_signals(action):"""?????? ?? ???????? ??????? ????? ??? ???? ???????"""if action == "STOP":led_left.on()led_right.on()elif action == "LEFT" or action == "AVOID LEFT" or action == "ROTATE LEFT":led_left.on()led_right.off()elif action == "RIGHT" or action == "AVOID RIGHT" or action == "ROTATE RIGHT":led_left.off()led_right.on()else:  # ?? ???? FORWARD ?? ?? ???? ???????led_left.off()led_right.off()

=========================================================

---------------- ROTATE FUNCTIONS -----------------------

=========================================================

def rotate_left(speed=0.8):

IN1.off()
IN2.on()

IN3.off()
IN4.on()

ENA.value = speed
ENB.value = speed
set_signals("ROTATE LEFT")

def rotate_right(speed=0.8):

IN1.on()
IN2.off()

IN3.on()
IN4.off()

ENA.value = speed
ENB.value = speed
set_signals("ROTATE right")

=========================================================

---------------- FORWARD DRIVE --------------------------

=========================================================

def move_car(steering_angle, gps_error=0, throttle=0.7):

global EMERGENCY_STOP
global CURRENT_SPEED
global ULTRA_STOP

if EMERGENCY_STOP:
    stop_car()
    return "Yolo STOP"

if abs(gps_error) > 25:

    gps_weight = 0.08
    cnn_weight = 0.15

else:

    gps_weight = 0.04
    cnn_weight = 0.35

final_steering = (
    (steering_angle * cnn_weight) +
    (gps_error * gps_weight)
)
IN1.on()
IN2.off()

IN3.off()
IN4.on()

if final_steering > 0.8:

    left_speed = 1.0
    right_speed = 0.67

    action = "RIGHT"
    

elif final_steering < -0.8:

    left_speed = 0.67
    right_speed = 1.0

    action = "LEFT"
    

else:

    left_speed = throttle
    right_speed = throttle

    action = "FORWARD"

speed = min(CURRENT_SPEED, throttle)

ENA.value = max(
    0,
    min(1, right_speed * RIGHT_CORRECTION * speed)
)

ENB.value = max(
    0,
    min(1, left_speed * LEFT_CORRECTION * speed)
)

return action

=========================================================

---------------- IMU SETUP ------------------------------

=========================================================

bus = smbus2.SMBus(1)

IMU_ADDR = 0x0dOFFSET = 16.31

def init_imu():

try:

    bus.write_byte_data(IMU_ADDR, 0x09, 0x1d)
    bus.write_byte_data(IMU_ADDR, 0x0b, 0x01)

    print("IMU Initialized")

except:

    print("IMU Error")

def get_heading():

try:

    data = bus.read_i2c_block_data(
        IMU_ADDR,
        0x00,
        6
    )

    x = (data[1] << 8) | data[0]
    y = (data[3] << 8) | data[2]

    if x > 32767:
        x -= 65536

    if y > 32767:
        y -= 65536

    heading = math.degrees(
        math.atan2(y, x)
    )

    if heading < 0:
        heading += 360

    return (heading + OFFSET) % 360

except:

    return None

=========================================================

---------------- GPS SETUP ------------------------------

=========================================================

GPS_PORT = "/dev/ttyAMA0"

gps_ser = serial.Serial(GPS_PORT,9600,timeout=1)

def read_gps():

while True:

    line = gps_ser.readline().decode(
        'utf-8',
        errors='ignore'
    )

    if "$GPGGA" in line:

        data = line.split(',')

        if len(data) > 6 and data[6] != '0':

            raw_lat = float(data[2])
            raw_lon = float(data[4])

            lat = int(raw_lat / 100) + \
                  (raw_lat % 100) / 60

            lon = int(raw_lon / 100) + \
                  (raw_lon % 100) / 60

            if data[3] == 'S':
                lat = -lat

            if data[5] == 'W':
                lon = -lon

            return lat, lon

=========================================================

---------------- NAVIGATION -----------------------------

=========================================================

def get_distance(lat1, lon1, lat2, lon2):

R = 6371000

phi1 = math.radians(lat1)
phi2 = math.radians(lat2)

dphi = math.radians(lat2 - lat1)
dlambda = math.radians(lon2 - lon1)

a = (
    math.sin(dphi / 2) ** 2 +
    math.cos(phi1) *
    math.cos(phi2) *
    math.sin(dlambda / 2) ** 2
)

return 2 * R * math.atan2(
    math.sqrt(a),
    math.sqrt(1 - a)
)


def get_ultra_dist():return ultra_sensor.distance * 100

def get_bearing(lat1, lon1, lat2, lon2):

y = math.sin(
    math.radians(lon2 - lon1)
) * math.cos(math.radians(lat2))


x = (
    math.cos(math.radians(lat1)) *
    math.sin(math.radians(lat2))
    -
    math.sin(math.radians(lat1)) *
    math.cos(math.radians(lat2)) *
    math.cos(math.radians(lon2 - lon1))
)

return (
    math.degrees(math.atan2(y, x)) + 360
) % 360

=========================================================

---------------- ROTATE TO HEADING ----------------------

=========================================================

def rotate_to_heading(target_heading):

while True:

    current = get_heading()

    if current is None:
        continue

    error = (
        target_heading -
        current +
        540
    ) % 360 - 180

    print(f"ROTATION ERROR: {error}")

    if abs(error) < 15:

        stop_car()

        print("HEADING ALIGNED")

        break

    if error > 0:

        rotate_right(0.7)

    else:

        rotate_left(0.7)

    time.sleep(0.05)

=========================================================

---------------- CNN MODEL ------------------------------

=========================================================

interpreter = tflite.Interpreter(model_path='model_float16.tflite')

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()output_details = interpreter.get_output_details()

def img_preprocess(img):

img = img[60:135, :, :]

img = cv2.cvtColor(
    img,
    cv2.COLOR_RGB2YUV
)

img = cv2.GaussianBlur(
    img,
    (3, 3),
    0
)

img = cv2.resize(img, (200, 66))

img = img / 255.0

return img

=========================================================

---------------- CAMERA STREAM --------------------------

=========================================================

cmd = ['rpicam-vid','-t', '0','--width', '640','--height', '480','--framerate', '20','--inline','--nopreview','--codec', 'yuv420','-o', '-']

pipe = subprocess.Popen(cmd,stdout=subprocess.PIPE,bufsize=10**8)

=========================================================

---------------- LIVE MAP -------------------------------

=========================================================

def process_yolo(frame):

global EMERGENCY_STOP
global CURRENT_SPEED

results = model.predict(
    frame,
    conf=0.45,
    imgsz=128,
    verbose=False
)

EMERGENCY_STOP = False

for r in results:

    for box in r.boxes:

        label = model.names[
            int(box.cls[0])
        ].lower()

        # ============================================
        # PERSON / CAR + ULTRASONIC SAFETY STOP
        # ============================================

        if label in ['person', 'car']:

            dist = get_ultra_dist()

            print(f"{label} detected | Distance: {dist:.1f} cm")

            if dist <= 40:

                EMERGENCY_STOP = True

                print("EMERGENCY STOP -> HUMAN/CAR TOO CLOSE")

        # ============================================
        # TRAFFIC LIGHTS / STOP SIGNS
        # ============================================

        elif label == 'traffic light red':

            EMERGENCY_STOP = True

            print("RED LIGHT STOP")

        elif label == 'stop sign':

            EMERGENCY_STOP = True

            print("STOP SIGN DETECTED")

        # ============================================
        # SPEED LIMITS
        # ============================================

        elif '30' in label:

            CURRENT_SPEED = 0.3

        elif '70' in label:

            CURRENT_SPEED = 0.7

        elif '100' in label:

            CURRENT_SPEED = 1.0

        # ============================================
        # GREEN LIGHT
        # ============================================

        elif label == 'green_light':

            EMERGENCY_STOP = False
            CURRENT_SPEED = 1.0

            print("GREEN LIGHT")

return results[0].plot()

=========================================================

---------------- QR SYSTEM ------------------------------

=========================================================

def start_qr_system():

print("\nSTARTING QR SYSTEM...")

pipe.terminate()
pipe.wait()

cv2.destroyAllWindows()

time.sleep(2)

picam2 = Picamera2()

config = picam2.create_preview_configuration(
    main={"size": (1080, 1920)}
)

picam2.configure(config)

picam2.start()

time.sleep(2)

qr_detector = cv2.QRCodeDetector()

start_time = time.time()

qr_found = False

while time.time() - start_time < 30:

    frame = picam2.capture_array()

    frame = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2BGR
    )

    qr_data, points, _ = qr_detector.detectAndDecode(frame)

    if qr_data:

        print("QR DETECTED:", qr_data)

        if qr_data == ALLOWED_QR:

            qr_found = True

            print("VALID QR")

            break

    cv2.imshow("QR Scanner", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

picam2.stop()

cv2.destroyAllWindows()
picam2.close()

if qr_found:

    print("OPENING BOX")

    # ????? ????? ???????
    servo.value = 0.5

    time.sleep(5)


    for i in range(AUTO_CLOSE_DELAY, 0, -1):

        print(f"Closing in {i}")

        time.sleep(1)

    servo.value = -0.5

    time.sleep(1)

    servo.value = None

    print("BOX CLOSED")

else:

    print("INVALID QR")

return qr_found

=========================================================

---------------- LIVE MAP -------------------------------

=========================================================

path_points = []

def update_map():

while True:

    if len(path_points) > 1:

        latest = path_points[-1]

        m = folium.Map(
            location=latest,
            zoom_start=18
        )

        folium.PolyLine(
            path_points,
            color='blue',
            weight=5
        ).add_to(m)

        folium.Marker(
            latest,
            tooltip="Car Position",
            icon=folium.Icon(color='red')
        ).add_to(m)

        m.save("live_map.html")

    time.sleep(2)



def ultrasonic_monitor():global ULTRA_STOP, OBSTACLE_NEAR, AVOID_DIRECTION, ULTRA_ACTIVE

while True:

    # ===============================
    # PAUSE MODE (QR / TARGET MODE)
    # ===============================
    if not ULTRA_ACTIVE:
        ULTRA_STOP = False
        OBSTACLE_NEAR = False
        AVOID_DIRECTION = "CENTER"

        ultra_servo.value = None  # stop servo movement
        time.sleep(0.2)
        continue

    # ===============================
    # NORMAL MODE (ACTIVE ULTRASONIC)
    # ===============================
    dist = get_ultra_dist()

    # STOP CONDITIONS
    if dist <= 40:
        ULTRA_STOP = True
        OBSTACLE_NEAR = True

    else:
        ULTRA_STOP = False
        OBSTACLE_NEAR = False

        # scan left-center-right
        scan = []

        for val, label in [(-0.5, "LEFT"), (0, "CENTER"), (0.5, "RIGHT")]:

            ultra_servo.value = val
            time.sleep(0.3)

            d = get_ultra_dist()
            scan.append((label, d))

        best = max(scan, key=lambda x: x[1])
        AVOID_DIRECTION = best[0]

    time.sleep(0.1)

=========================================================

---------------- MAIN NAVIGATION ------------------------

=========================================================

def navigate(target_lat, target_lon):global pipe, ULTRA_ACTIVE, ROBOT_IDfront_light.on() # ????? ?????? ??????? ?????? ?????

init_imu()

print("Getting Start Position...")

start_lat, start_lon = read_gps()

print("START POSITION SAVED")

webbrowser.open("live_map.html")

map_thread = threading.Thread(
    target=update_map,
    daemon=True
)
map_thread.start()

# =====================================================
# FACE TARGET USING IMU
# =====================================================

heading = get_bearing(
    start_lat,
    start_lon,
    target_lat,
    target_lon
)

rotate_to_heading(heading)

# =====================================================
# GO TARGET THEN RETURN HOME
# =====================================================

targets = [
    (target_lat, target_lon),
    (start_lat, start_lon)
]

for idx, (goal_lat, goal_lon) in enumerate(targets):

    if idx == 0:
        print("GOING TO TARGET")
    else:
        print("RETURNING HOME")

        current_lat, current_lon = read_gps()

        return_heading = get_bearing(
            current_lat,
            current_lon,
            start_lat,
            start_lon
        )

        rotate_to_heading(return_heading)

    while True:

        curr_lat, curr_lon = read_gps()
        send_tracking(curr_lat, curr_lon)

        path_points.append((curr_lat, curr_lon))

        distance = get_distance(
            curr_lat,
            curr_lon,
            goal_lat,
            goal_lon
        )

        target_bearing = get_bearing(
            curr_lat,
            curr_lon,
            goal_lat,
            goal_lon
        )

        current_heading = get_heading()

        if current_heading is None:
            continue

        error = (
            target_bearing -
            current_heading +
            540
        ) % 360 - 180

        # =================================================
        # CAMERA
        # =================================================

        raw_image = pipe.stdout.read(
            640 * 480 * 3 // 2
        )

        if not raw_image:
            break

        yuv = np.frombuffer(
            raw_image,
            dtype=np.uint8
        ).reshape((480 * 3 // 2, 640))

        frame = cv2.cvtColor(
            yuv,
            cv2.COLOR_YUV2BGR_I420
        )

        # =================================================
        # YOLO OBJECT DETECTION
        # =================================================

        annotated_frame = process_yolo(frame)

        # =================================================
        # CNN
        # =================================================

        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        processed = img_preprocess(image_rgb)

        image_input = np.array(
            [processed],
            dtype=np.float32
        )

        interpreter.set_tensor(
            input_details[0]['index'],
            image_input
        )
        interpreter.invoke()

        output_data = interpreter.get_tensor(
            output_details[0]['index']
        )

        steering_angle = float(output_data.flatten()[0])

        # =================================================
        # ULTRASONIC OBSTACLE AVOIDANCE
        # =================================================

        if OBSTACLE_NEAR:

            stop_car()
            if AVOID_DIRECTION == "LEFT":
                rotate_left(0.7)
                action = "AVOID LEFT"
                set_signals(action)
                time.sleep(0.25)
                continue

            elif AVOID_DIRECTION == "RIGHT":
                rotate_right(0.7)
                action = "AVOID RIGHT"
                set_signals(action)
                time.sleep(0.25)
                continue

        # =================================================
        # GPS + IMU STEERING
        # =================================================

        if abs(error) > 35:

            if error > 0:
                rotate_right()
                action = "ROTATE RIGHT"
            else:
                rotate_left()
                action = "ROTATE LEFT"

        else:

            action = move_car(
                steering_angle,
                gps_error=error,
                throttle=0.75
            )
        if "ROTATE" in action or "AVOID" in action:
            set_signals(action)
		
        # =================================================
        # DISPLAY
        # =================================================

        cv2.putText(
            annotated_frame,
            f"Distance: {distance:.2f} m",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Heading: {current_heading:.1f}",
            (20, 80),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 255),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Error: {error:.1f}",
            (20, 120),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2
        )

        cv2.putText(
            annotated_frame,
            f"Action: {action}",
            (20, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 0, 0),
            2
        )

        cv2.imshow("DELIVARO AI SYSTEM", annotated_frame)

        print(
            f"Dist:{distance:.2f}m | "
            f"Target:{target_bearing:.1f} | "
            f"Heading:{current_heading:.1f} | "
            f"Error:{error:.1f} | "
            f"{action}"
        )

        # =================================================
        # REACHED TARGET
        # =================================================

        if distance < 3:

            stop_car()
            if idx == 0:

                print("TARGET REACHED")
                print("DISABLING ULTRASONIC FOR QR MODE")
                try:
                    print("?? Sending Arrived Status to Server...")
                    requests.patch(f"https://exposed-manor-mba-robertson.trycloudflare.com/api/admin/orders/{int(sys.argv[3])}/status/", json={"status": "arrived"}, headers=HEADERS, timeout=3)
                    print("?? Server Notified Successfully!")
                except Exception as status_error:
                    print(f"?? Status update skipped: {status_error}")

                print("DISABLING ULTRASONIC FOR QR MODE")
                # =========================
                # DISABLE ULTRASONIC
                # =========================
                ULTRA_ACTIVE = False

                time.sleep(0.5)

                # =========================
                # QR SYSTEM
                # =========================
                start_qr_system()

                # =========================
                # RESTART CAMERA PIPELINE
                # =========================
                pipe = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    bufsize=10**8
                )

                # =========================
                # RE-ENABLE ULTRASONIC
                # =========================
                print("RE-ENABLING ULTRASONIC")

                ULTRA_ACTIVE = True

                time.sleep(2)

            else:

                print("HOME REACHED")

            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            stop_car()
            return

stop_car()
pipe.terminate()
cv2.destroyAllWindows()



=========================================================

TEst

=========================================================

????? ??????? ????????? ??? ???? ???? ??? UnboundLocalError

ROBOT_ID = 1

def login():global HEADERStry:print("?? Connecting to Cloudflare Tunnel Server...")# ?? ?? ????? ?????? ??? ??? ?????? ?????? ???????response = requests.post("https://exposed-manor-mba-robertson.trycloudflare.com/api/auth/login/",json={"email": "robot@delivero.com","password": "123#456"},timeout=4)token = response.json()['tokens']['access']HEADERS = {"Authorization": f"Bearer {token}"}print("? LOGIN SUCCESS: Live Cloud Telemetry Active!")except Exception as e:# ????? ??????? ?? ?????? ????? ??? ??? Login ?????? ??????HEADERS = {"Authorization": "Bearer bypass_test_token"}print(f"?? Cloud Connection Failed ({e}). Running in OFFLINE Mode safely!")

def send_tracking(lat, lng):global HEADERS, ROBOT_IDtry:url = f"https://exposed-manor-mba-robertson.trycloudflare.com/api/robots/{ROBOT_ID}/telemetry/"

    # ????? ????? ???????
    response = requests.patch(
        url,
        json={
            "latitude": lat,
            "longitude": lng,
            "battery_level": 93.0,
            "speed": 12.0,
            "status": "in_transit"
        },
        headers=HEADERS,
        timeout=1  
    )
    
    # ?? ?????? ??????? ??????? ??? ?????:
    if response.status_code in [200, 204]:
        # ?? ??????? ??????? ?????
        print(f"?? [LIVE TELEMETRY] Sent Successfully! Robot [{ROBOT_ID}] is at Lat: {lat}, Lng: {lng} (Status: {response.status_code})")
    else:
        # ?? ??????? ?? ?? ??????? ????? (?? ??? 401 ?? 404 ???? ????? ????)
        print(f"?? [TELEMETRY ERROR] Server received but rejected it! Status: {response.status_code} | Reason: {response.text}")

except Exception as e:
    # ?? ???? ??? ?? ?????? ????? ??? ?????? ????
    print(f"?? [TELEMETRY SKIPPED] Failed to reach server. Network Lag or Server Offline! Error: {e}")

----------------------- START ---------------------------

=========================================================

if name == "main":

# 1. ????? ?????? ?????? ???? ??????? ????????
login()

# 2. ????? ???? ??? Ultrasonic ??????? ??????? ?? ???????
ultra_thread = threading.Thread(
    target=ultrasonic_monitor,
    daemon=True
)
ultra_thread.start()

try:
    # =========================================
    # GET TARGET, QR & ROBOT ID FROM SERVER
    # =========================================
    # ??? robot_controller ????? 5 ????????: script.py lat lng qr robot_id
    if len(sys.argv) >= 5:
        target_lat = float(sys.argv[1])
        target_lon = float(sys.argv[2])
        ALLOWED_QR = sys.argv[3]   # ????? ?????????? ?????? ???????
        ROBOT_ID = sys.argv[4]     # ?? ??? ??? Robot ID ??????? ?????? ?? ???????
        print(f"?? Dynamic Robot ID Locked: {ROBOT_ID}")
        print(f"-> Dynamic QR Mode: Box will unlock only with: {ALLOWED_QR}")

    elif len(sys.argv) == 4:
        # ?? ??? Controller ??? 4 ???????? ?? (???? ??? ID)
        target_lat = float(sys.argv[1])
        target_lon = float(sys.argv[2])
        ALLOWED_QR = sys.argv[3]
        ROBOT_ID = 1  # ?????? ?????????? ??????????
        print(f"-> Dynamic QR Mode: Box will unlock only with: {ALLOWED_QR}")
        print(f"-> Warning: No Robot ID received, using fallback ID: {ROBOT_ID}")

    elif len(sys.argv) == 3:
        # ?? ?????? ?????? ?? ??????? ??? ???????? ???
        target_lat = float(sys.argv[1])
        target_lon = float(sys.argv[2])
        ALLOWED_QR = "https://qrco.de/bgju8a" # ??? QR ?????????
        ROBOT_ID = 1
        print("-> Warning: No QR received from backend, using fallback default.")

    else:
        print("No Target Coordinates Received")
        exit()

    print(f"\n?? TARGET RECEIVED & LOCKED:")
    print(f"Robot ID : {ROBOT_ID}")
    print(f"Latitude : {target_lat}")
    print(f"Longitude: {target_lon}")
    print(f"Target QR : {ALLOWED_QR}")

    # 3. ??????? ???? ??????? ??????? ?????? ??? ?????
    navigate(
        target_lat,
        target_lon
    )

except KeyboardInterrupt:

    print("\n?? STOPPING SYSTEM VIA USER INTERRUPT...")

    # ????? ???? ???????? ?????? ????? ?????? ??????? ?????
    stop_car()

    # ????? ????? ???? ??????? ???????? ?????
    try:
        pipe.terminate()
        pipe.wait()
    except:
        pass

    # ????? ???? ????? OpenCV ???????? ?? YOLO
    cv2.destroyAllWindows()

    # ????? ?????? ?????? ??? GPIO ????????? ??? ???? ?????? ?????
    try:
        ENA.close()
        ENB.close()

        IN1.close()
        IN2.close()
        IN3.close()
        IN4.close()

        servo.close()
        gps_ser.close()
        bus.close()
        
        # ????? ???????? ??????? ?????? ???????
        led_left.close()
        led_right.close()

        # ????? ?????? ??????? ?????? ?????? ?????? ?????? ?????
        front_light.off()   
        front_light.close() 

    except:
        pass

    print("?? SYSTEM SAFELY STOPPED")