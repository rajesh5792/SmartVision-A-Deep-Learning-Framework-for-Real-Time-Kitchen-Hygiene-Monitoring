# SmartVision-A-Deep-Learning-Framework-for-Real-Time-Kitchen-Hygiene-Monitoring
SmartVision is a real-time safety monitoring system that leverages computer vision and deep learning to detect Personal Protective Equipment (PPE) violations such as the absence of gloves, masks, and hairnets. The system processes live video streams using a YOLO-based object detection model to identify safety risks with high accuracy. It integrates automated email alerts and a web-based dashboard for real-time monitoring, alert visualization, and data management. By combining intelligent detection with responsive alert mechanisms, SmartVision provides an efficient and scalable solution for improving safety compliance in controlled environments.

Features --
  Real-time object detection using YOLO
  PPE violation detection (no_mask, no_gloves, no_hairnet)
  Live camera monitoring
  Automated email alert system
  Web dashboard for alerts and statistics
  Detection history storage using database
  Start/Stop monitoring control
  
Tech Stack --
  Frontend: HTML, CSS
  Backend: Python (Flask)
  Computer Vision: OpenCV
  Model: YOLO (Ultralytics)
  Database: SQLite
  Email Service: SMTP
  
System Workflow --
Step 1:  Capture video from camera
Step 2:  Preprocess frames
Step 3:  Detect objects using YOLO
Step 4:  Check violation duration
Step 5:  Generate alerts
Step 6:  Send email notification
Step 7:  Store data in database
Step 8:  Display results on dashboard

Model Performance--
  mAP: 0.87
  Precision: 0.85
  Recall: 0.83

📧 Email Alert System--
  Sends real-time alerts on violation detection
  Includes object type, confidence score, and timestamp

Authors--

  Rajesh Kannan L, Jeya Mithra K, Meenakshi B, Surarapu Ashish 
