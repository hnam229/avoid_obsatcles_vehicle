import RPi.GPIO as GPIO
import time
import cv2
import threading
from flask import Flask, render_template, Response, jsonify, request

app = Flask(__name__)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

obstacle_avoidance_running = False

# Defining motor pins
in1 = 13 
in2 = 19
in3 = 26
in4 = 21
ena = 16
enb = 20
TRIG_FRONT = 17
ECHO_FRONT = 27
TRIG_LEFT = 23
ECHO_LEFT = 24
TRIG_RIGHT = 5
ECHO_RIGHT = 6

#Set up GPIO pins
GPIO.setup(TRIG_FRONT, GPIO.OUT)
GPIO.setup(ECHO_FRONT, GPIO.IN)
GPIO.setup(TRIG_LEFT, GPIO.OUT)
GPIO.setup(ECHO_LEFT, GPIO.IN)
GPIO.setup(TRIG_RIGHT, GPIO.OUT)
GPIO.setup(ECHO_RIGHT, GPIO.IN)

#Set GPIO direction (IN / OUT)
GPIO.setup(in1,GPIO.OUT)
GPIO.setup(in2,GPIO.OUT)
GPIO.setup(in3,GPIO.OUT)
GPIO.setup(in4,GPIO.OUT)
GPIO.setup(ena,GPIO.OUT)
GPIO.setup(enb,GPIO.OUT)
pb = GPIO.PWM(ena, 16)
pa = GPIO.PWM(enb, 16)
pa.start(0)
pb.start(0)
time.sleep(3)

# Motor control functions
def move_forward():
    GPIO.output(in1, 1)
    GPIO.output(in2, 0)
    GPIO.output(in3, 0)
    GPIO.output(in4, 1)
    pa.ChangeDutyCycle(16)
    pb.ChangeDutyCycle(16)
    pass

def move_backward():
    GPIO.output(in1, 0)
    GPIO.output(in2, 1)
    GPIO.output(in3, 1)
    GPIO.output(in4, 0)
    pa.ChangeDutyCycle(16)
    pb.ChangeDutyCycle(16)
    pass

def turn_left():
    GPIO.output(in1, 0)
    GPIO.output(in2, 0)
    GPIO.output(in3, 0)
    GPIO.output(in4, 1)
    pa.ChangeDutyCycle(16)
    pb.ChangeDutyCycle(0)
    pass

def turn_right():
    GPIO.output(in1, 1)
    GPIO.output(in2, 0)
    GPIO.output(in3, 0)
    GPIO.output(in4, 0)
    pa.ChangeDutyCycle(0)
    pb.ChangeDutyCycle(16)
    pass

def stop():
    GPIO.output(in1, 0)
    GPIO.output(in2, 0)
    GPIO.output(in3, 0)
    GPIO.output(in4, 0)
    pa.ChangeDutyCycle(0)
    pb.ChangeDutyCycle(0)
    pass

def avoid_right():
    stop()
    time.sleep(2)
    move_backward()
    time.sleep(1)
    stop()
    time.sleep(2)
    turn_right()
    time.sleep(0.5)
    stop()
    time.sleep(2)
    pass

def avoid_left():
    stop()
    time.sleep(2)
    move_backward()
    time.sleep(1)
    stop()
    time.sleep(2)
    turn_left()
    time.sleep(0.5)
    stop()
    time.sleep(2)
    pass

def measure_distance(trig_pin, echo_pin):
    # Send ultrasonic pulse
    GPIO.output(trig_pin, True)
    time.sleep(0.00001)
    GPIO.output(trig_pin, False)

    # Wait for echo response
    while GPIO.input(echo_pin) == 0:
        pulse_start = time.time()

    while GPIO.input(echo_pin) == 1:
        pulse_end = time.time()

    # Calculate distance
    pulse_duration = pulse_end - pulse_start
    distance = pulse_duration * 17150
    distance = round(distance, 2)
    return distance

def initialize_camera():
    camera = cv2.VideoCapture(0)

    # Set camera properties for optimization
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    camera.set(cv2.CAP_PROP_FPS, 30)
    
    return camera

def generate_frames(camera):
    while True:
        # Capture a frame from the camera
        success, frame = camera.read()
        if not success:
            break
            
        # Flip the frame vertically due to hardware set up
        frame = cv2.flip(frame, 0)

        # Compress the frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame = jpeg.tobytes()

        # Yield the frame for streaming
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    camera = initialize_camera()
    return Response(generate_frames(camera), mimetype='multipart/x-mixed-replace; boundary=frame')

def obstacle_avoidance():
    global obstacle_avoidance_running
    try:
        while obstacle_avoidance_running:
            distance1 = measure_distance(TRIG_FRONT, ECHO_FRONT)
            distance2 = measure_distance(TRIG_LEFT, ECHO_LEFT)
            distance3 = measure_distance(TRIG_RIGHT, ECHO_RIGHT)

            if distance1 < 25:
                if distance2 > 20:
                    stop()
                    avoid_left()
                    stop()
                elif distance3 > 20:
                    stop()
                    avoid_right()
                    stop()
                else:
                    move_backward()
                    time.sleep(2)
                    stop()
            elif distance2 < 20:
                if distance1 < 25 or distance3 < 20:
                    move_backward()
                    time.sleep(2)
                    stop()
                else:
                    stop()
                    avoid_right()
                    stop()
            elif distance3 < 20:
                if distance1 < 25 or distance2 < 20:
                    move_backward()
                    time.sleep(2)
                    stop()
                else:
                    stop()
                    avoid_left()
                    stop()
            else:
                move_forward()
        time.sleep(0.1)
    except KeyboardInterrupt:
        GPIO.cleanup()

def stop_obstacle_avoidance():
    global obstacle_avoidance_running
    obstacle_avoidance_running = False

@app.route('/start_vehicle')
def start_vehicle():
    global obstacle_avoidance_running
    obstacle_avoidance_running = True
    threading.Thread(target=obstacle_avoidance).start()
    return jsonify({'message': 'Vehicle started'})

@app.route('/stop_vehicle')
def stop_vehicle():
    global obstacle_avoidance_running
    stop()  # Stop the motors when the vehicle is stopped
    stop_obstacle_avoidance()
    return jsonify({'message': 'Vehicle stopped'})

@app.route('/moveForward')
def moveForward():
    move_forward()
    time.sleep(1)
    stop()
    return jsonify({'message': 'Moving Forward'})
    
@app.route('/moveBackward')
def moveBackward():
    move_backward()
    time.sleep(1.5)
    stop()
    return jsonify({'message': 'Moving Backward'})

@app.route('/moveLeft')
def moveLeft():
    turn_left()
    time.sleep(1)
    stop()
    return jsonify({'message': 'Moving Left'})
    
@app.route('/moveRight')
def moveRight():
    turn_right()
    time.sleep(1)
    stop()
    return jsonify({'message': 'Moving Right'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

