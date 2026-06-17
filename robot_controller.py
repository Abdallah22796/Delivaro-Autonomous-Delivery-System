import time
import threading
import requests
import serial # ???? ??? ???? pyserial
from flask import Flask, request, jsonify

BASE_URL = "https://exposed-manor-mba-robertson.trycloudflare.com"
ROBOT_ID = None
ROBOT_EMAIL = "robot@delivero.com"
ROBOT_PASSWORD = "123#456"

# ??????? ??? GPS ?????? ?? (?? ????? ???? ????)
GPS_PORT = '/dev/ttyAMA0'
BAUD_RATE = 9600

# ???? ??????? ???????? ??? ???????
BASE_LAT = None
BASE_LNG = None 
LOCK_PIN = 18



token = None
headers = {}    
current_mission = None


def convert_to_decimal(coord, direction):
    if not coord or coord == "":
        return None
    try:
        degrees = int(float(coord) / 100)
        minutes = float(coord) - degrees * 100
        result = degrees + (minutes / 60)
        if direction in ['S', 'W']:
            result = -result
        return result
    except:
        return None

def get_gps_location():

    try:

        ser = serial.Serial(
            GPS_PORT,
            BAUD_RATE,
            timeout=1
        )

        for _ in range(15):

            line = ser.readline().decode(
                'utf-8',
                errors='ignore'
            ).strip()

            if "$GPGGA" in line:

                data = line.split(',')

                if len(data) >= 6 and data[6] != "0":

                    lat = convert_to_decimal(
                        data[2],
                        data[3]
                    )

                    lng = convert_to_decimal(
                        data[4],
                        data[5]
                    )

                    if lat and lng:

                        ser.close()

                        return lat, lng

        ser.close()

    except Exception as e:

        print(f"GPS Hardware Error: {e}")

    return None, None

app = Flask(__name__)

@app.route('/new-mission/', methods=['POST'])
def new_mission():
    global current_mission, ROBOT_ID
    mission_data = request.json
    new_id = mission_data.get('robot_id')
    if new_id:
        ROBOT_ID = new_id
        print(f"\n?? Robot ID Updated: {ROBOT_ID}")

    print(f"\n? New Mission! Order ID: {mission_data.get('order_id')}")
    current_mission = mission_data 
    threading.Thread(target=execute_delivery, args=(mission_data,)).start()
    return jsonify({"status": "Mission received!"})


def login():
    global token, headers
    print("?? Logging in...")
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login/", 
            json={"email": ROBOT_EMAIL, "password": ROBOT_PASSWORD}, timeout=10)
        if response.status_code == 200:
            token = response.json()['tokens']['access']
            headers = {"Authorization": f"Bearer {token}"}
            print("? Login successful!")
            return True
        return False
    except Exception as e:
        print(f"? Login error: {e}")
        return False


def send_telemetry(lat, lng, battery, speed, status):
    if ROBOT_ID is None: return
    try:
        requests.patch(f"{BASE_URL}/api/robots/{ROBOT_ID}/telemetry/",
            json={"latitude": lat, "longitude": lng, "battery_level": battery, "speed": speed, "status": status},
            headers=headers, timeout=5)
        print(f"?? Sent Telemetry: lat={lat}, lng={lng}")
    except: pass

def calculate_distance(lat1, lng1, lat2, lng2):
    import math
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi, d_lam = math.radians(lat2-lat1), math.radians(lng2-lng1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def navigate_to_destination(order_id, dest_lat, dest_lng):
    print(f"\n?? Heading to customer...")
    while True:
        current_lat, current_lng = get_gps_location()
        dist = calculate_distance(current_lat, current_lng, dest_lat, dest_lng)
        print(f"?? Distance: {dist:.1f}m")
        send_telemetry(current_lat, current_lng, 85.0, 12.5, "in_transit")
        if dist < 5:
            print("? Arrived at Customer!")
            break
        time.sleep(5)
import subprocess

def execute_delivery(mission):
    dest_lat = mission['delivery_address']['latitude']
    dest_lng = mission['delivery_address']['longitude']

    # 1. ??????? ??? QR ?????????? ?????? ?? ??????? (?? ?? ????? ????? ??? order_id ?? ???????)
    qr_data = mission.get('qr_code', mission.get('order_id'))

    print("\n?? Starting Autonomous Car System...")

    try:
        print("\n==============================")
        print("MISSION RECEIVED:")
        print(mission)
        print(f"DEST LAT: {dest_lat}")
        print(f"DEST LNG: {dest_lng}")
        print(f"ORDER QR: {qr_data}") # ?????? ?? ??????????
        print("==============================\n")

        # 2. ????? ??? subprocess ?????? str(qr_data) ?? ??????? ????
        subprocess.run([
            "/home/raspberrypi/Desktop/OD/GPenv/bin/python",
            "/home/raspberrypi/Desktop/OD/clonee.py",
            str(dest_lat),
            str(dest_lng),
            str(qr_data),  # <--- ??????? ??? (????? ??? QR)
            str(ROBOT_ID)
        ])

    except Exception as e:
        print(f"Error running car system: {e}")
def return_to_base():
    print(f"\n?? Returning to Base...")
    while True:
        curr_lat, curr_lng = get_gps_location()
        dist = calculate_distance(curr_lat, curr_lng, BASE_LAT, BASE_LNG)
        send_telemetry(curr_lat, curr_lng, 80.0, 12.5, "returning")
        if dist < 5:
            send_telemetry(BASE_LAT, BASE_LNG, 80.0, 0.0, "idle")
            print("? Back at Base!")
            break
        time.sleep(5)

def set_home_location():
    """????? ???? ??????? ?????? ???????"""
    global BASE_LAT, BASE_LNG
    print("?? Determining Home location from Serial GPS...")
    # ???????? ??? ?????? ??? ???????? (?? None)
    BASE_LAT, BASE_LNG = get_gps_location()
    print(f"?? Home set to: {BASE_LAT}, {BASE_LNG}")


def main():
    if not login(): return
    
    # ????? ????? ?????
    set_home_location()

    # ????? ??????? ?? ???????
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000), daemon=True).start()
    
    print("\n? Waiting for missions...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()