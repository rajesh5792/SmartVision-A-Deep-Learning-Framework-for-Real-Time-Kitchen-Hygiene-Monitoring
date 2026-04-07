import os
import sqlite3
import cv2
import threading
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from ultralytics import YOLO
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
import base64
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'

# Global variables for camera control
camera_active = False
camera_thread = None
camera = None
current_frame = None
current_user_id = None
current_user_email = None
last_detection_time = {}
detection_history = []
alerts_queue = []
frame_lock = threading.Lock()

# SMTP Configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 465
SMTP_USERNAME = 'hariviki7895@gmail.com'
SMTP_PASSWORD = 'kmvwrwphnjsfamtu'

# Initialize YOLO models
try:
    print("Loading YOLO models...")
    model_food = YOLO("food.pt")
    model_safety = YOLO("mask.pt")
    print("Models loaded successfully!")
except Exception as e:
    print(f"Error loading models: {e}")
    print("Using demo mode...")
    model_food = None
    model_safety = None

# Database initialization
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  alert_type TEXT NOT NULL,
                  item TEXT NOT NULL,
                  confidence REAL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Email sending function
def send_alert_email(user_email, alert_type, item, confidence=None):
    """Send email alert for continuous detections"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🚨 ALERT: {item} Detected"
        msg['From'] = SMTP_USERNAME
        msg['To'] = user_email
        
        # Email content
        time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #dc3545; color: white; padding: 20px; text-align: center; border-radius: 10px 10px 0 0; }}
                .content {{ background: #f8f9fa; padding: 30px; border-radius: 0 0 10px 10px; }}
                .alert-box {{ background: white; padding: 20px; border-left: 5px solid #28a745; margin: 20px 0; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🚨 DETECTION ALERT</h2>
                    <p>AI Detection System Notification</p>
                </div>
                <div class="content">
                    <h3>Continuous Detection Alert</h3>
                    
                    <div class="alert-box">
                        <p><strong>Alert Type:</strong> {alert_type.upper()}</p>
                        <p><strong>Item Detected:</strong> {item}</p>
                        {f'<p><strong>Confidence Level:</strong> {confidence:.2%}</p>' if confidence else ''}
                        <p><strong>Detection Time:</strong> {time_str}</p>
                        <p><strong>User Account:</strong> {user_email}</p>
                    </div>
                    
                    <p><em>This item has been continuously detected for 3+ seconds.</em></p>
                    <p><em>This is an automated alert from your AI Detection System.</em></p>
                    
                    <div class="footer">
                        <p>© 2024 AI Detection System. All rights reserved.</p>
                        <p>This email was sent automatically. Please do not reply.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach HTML content
        msg.attach(MIMEText(html, 'html'))
        
        # Send email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        print(f"📧 Email alert sent to {user_email} - {item} detected")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

# Camera processing thread
def camera_processing():
    global camera_active, camera, current_frame, current_user_id, current_user_email
    global last_detection_time, detection_history, alerts_queue
    
    camera = cv2.VideoCapture(0)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    if not camera.isOpened():
        print("Cannot open camera")
        return
    
    print("Camera started successfully!")
    
    while camera_active:
        ret, frame = camera.read()
        if not ret:
            print("Failed to grab frame")
            break
        
        display_frame = frame.copy()
        current_time = time.time()
        frame_alerts = []
        time.sleep(10)
        # Process food detections if model is loaded
        if model_food:
            try:
                results = model_food(frame)
                
                if results and len(results) > 0:
                    for r in results:
                        if r.boxes is not None:
                            for box in r.boxes:
                                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                                cls_id = int(box.cls[0])
                                conf = float(box.conf[0])
                                label_name = r.names[cls_id] if hasattr(r, 'names') else f"Food_{cls_id}"
                                label = f"{label_name} {conf:.2f}"
                                
                                # Draw bounding box (Yellow for food)
                                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                                cv2.putText(display_frame, label, (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                                
                                # Check for 3-second continuous detection
                                alert_key = f"food_{label_name}"
                                if alert_key not in last_detection_time:
                                    last_detection_time[alert_key] = current_time
                                
                                if (current_time - last_detection_time[alert_key]) >= 3:
                                    # Send alert
                                    alert_data = {
                                        'type': 'food',
                                        'item': label_name,
                                        'confidence': conf,
                                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                                        'email_sent': False
                                    }
                                    
                                    # Send email if user is logged in
                                    if current_user_email:
                                        email_sent = send_alert_email(
                                            current_user_email, 
                                            'food', 
                                            label_name, 
                                            conf
                                        )
                                        alert_data['email_sent'] = email_sent
                                    
                                    frame_alerts.append(alert_data)
                                    last_detection_time[alert_key] = current_time
                                    
            except Exception as e:
                print(f"Error in food detection: {e}")
        
        # Process safety detections if model is loaded
        if model_safety:
            try:
                results = model_safety(frame)
                
                if results and len(results) > 0:
                    for r in results:
                        if r.boxes is not None:
                            for box in r.boxes:
                                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                                cls_id = int(box.cls[0])
                                conf = float(box.conf[0])
                                label_name = r.names[cls_id] if hasattr(r, 'names') else f"Safety_{cls_id}"
                                label = f"{label_name} {conf:.2f}"
                                
                                # Draw bounding box (Cyan for safety)
                                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                                cv2.putText(display_frame, label, (x1, y1 - 10),
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
                                
                                # Check for 3-second continuous detection
                                alert_key = f"safety_{label_name}"
                                if alert_key not in last_detection_time:
                                    last_detection_time[alert_key] = current_time
                                
                                if (current_time - last_detection_time[alert_key]) >= 3:
                                    # Send alert
                                    alert_data = {
                                        'type': 'safety',
                                        'item': label_name,
                                        'confidence': conf,
                                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                                        'email_sent': False
                                    }
                                    
                                    # Send email if user is logged in
                                    if current_user_email:
                                        email_sent = send_alert_email(
                                            current_user_email, 
                                            'safety', 
                                            label_name, 
                                            conf
                                        )
                                        alert_data['email_sent'] = email_sent
                                    
                                    frame_alerts.append(alert_data)
                                    last_detection_time[alert_key] = current_time
                                    
            except Exception as e:
                print(f"Error in safety detection: {e}")
        
        # If no models loaded, show demo text
        if not model_food and not model_safety:
            cv2.putText(display_frame, "DEMO MODE - No YOLO models loaded", 
                       (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, "Place YOLO models (food.pt, mask.pt) in project folder", 
                       (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Add timestamp
        cv2.putText(display_frame, datetime.now().strftime('%H:%M:%S'), 
                   (10, display_frame.shape[0] - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add status text
        status_text = f"User: {current_user_email or 'Not logged in'}"
        cv2.putText(display_frame, status_text, 
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Store alerts
        if frame_alerts:
            with frame_lock:
                for alert in frame_alerts:
                    detection_history.append(alert)
                    alerts_queue.append(alert)
                    
                    # Store in database
                    if current_user_id:
                        conn = get_db()
                        conn.execute('''INSERT INTO alerts (user_id, alert_type, item, confidence)
                                      VALUES (?, ?, ?, ?)''',
                                    (current_user_id, alert['type'], alert['item'], alert.get('confidence', 0.0)))
                        conn.commit()
                        conn.close()
            
            # Keep only recent history
            if len(detection_history) > 100:
                detection_history = detection_history[-100:]
            if len(alerts_queue) > 50:
                alerts_queue = alerts_queue[-50:]
        
        # Convert frame to JPEG
        _, buffer = cv2.imencode('.jpg', display_frame)
        with frame_lock:
            current_frame = buffer.tobytes()
        
        time.sleep(0.03)  # ~30 FPS
    
    if camera:
        camera.release()
        print("Camera released")
    
    # Clear frame
    with frame_lock:
        current_frame = None

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if not username or not email or not password:
            return render_template('register.html', error='All fields are required!')
        
        hashed_password = generate_password_hash(password)
        
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                        (username, email, hashed_password))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username or email already exists!')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['email'] = user['email']
            global current_user_id, current_user_email
            current_user_id = user['id']
            current_user_email = user['email']
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials!')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get recent alerts for this user
    conn = get_db()
    alerts = conn.execute('''SELECT * FROM alerts WHERE user_id = ? 
                          ORDER BY timestamp DESC LIMIT 10''',
                         (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('dashboard.html', 
                          username=session['username'],
                          email=session['email'],
                          alerts=alerts)

@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    def generate():
        while True:
            with frame_lock:
                if current_frame is not None:
                    frame = current_frame
                else:
                    # Generate a blank frame
                    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    blank_frame[:] = (40, 40, 40)
                    cv2.putText(blank_frame, "Camera Off", (200, 240), 
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    _, buffer = cv2.imencode('.jpg', blank_frame)
                    frame = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03)
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/start_camera', methods=['POST'])
def start_camera():
    global camera_active, camera_thread
    
    if not camera_active:
        camera_active = True
        camera_thread = threading.Thread(target=camera_processing)
        camera_thread.daemon = True
        camera_thread.start()
        time.sleep(1)  # Give camera time to start
        return jsonify({'status': 'success', 'message': 'Camera started'})
    
    return jsonify({'status': 'error', 'message': 'Camera already running'})

@app.route('/stop_camera', methods=['POST'])
def stop_camera():
    global camera_active, camera, current_frame
    
    if camera_active:
        camera_active = False
        
        # Wait for thread to finish
        if camera_thread:
            camera_thread.join(timeout=2)
        
        # Clear current frame
        with frame_lock:
            current_frame = None
        
        return jsonify({'status': 'success', 'message': 'Camera stopped'})
    
    return jsonify({'status': 'error', 'message': 'Camera already stopped'})

@app.route('/camera_status')
def camera_status():
    global camera_active
    return jsonify({'active': camera_active})

@app.route('/get_alerts')
def get_alerts():
    """Get recent alerts for AJAX updates"""
    global alerts_queue
    
    with frame_lock:
        recent_alerts = alerts_queue.copy()
        alerts_queue.clear()  # Clear after sending
    
    return jsonify({'alerts': recent_alerts})

@app.route('/get_recent_alerts')
def get_recent_alerts():
    """Get alerts from database"""
    if 'user_id' not in session:
        return jsonify({'alerts': []})
    
    conn = get_db()
    alerts = conn.execute('''SELECT * FROM alerts WHERE user_id = ? 
                          ORDER BY timestamp DESC LIMIT 20''',
                         (session['user_id'],)).fetchall()
    conn.close()
    
    alert_list = []
    for alert in alerts:
        alert_list.append({
            'id': alert['id'],
            'type': alert['alert_type'],
            'item': alert['item'],
            'confidence': alert['confidence'],
            'timestamp': alert['timestamp'],
            'email_sent': True  # Assuming all stored alerts had emails sent
        })
    
    return jsonify({'alerts': alert_list})

@app.route('/logout')
def logout():
    global camera_active, current_user_id, current_user_email, camera
    
    # Stop camera if running
    if camera_active:
        camera_active = False
        if camera_thread:
            camera_thread.join(timeout=2)
        if camera:
            camera.release()
    
    current_user_id = None
    current_user_email = None
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)