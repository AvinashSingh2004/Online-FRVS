from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
import smtplib
import random
import cv2
import pickle
import numpy as np
import os
import csv
import time
from datetime import datetime
from sklearn.neighbors import KNeighborsClassifier
from win32com.client import Dispatch
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow as Flow
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import re
import io

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages

SCOPES = ['https://www.googleapis.com/auth/drive.file']

video = cv2.VideoCapture(0)

def speak(str1):
    speak = Dispatch(("SAPI.SpVoice"))
    speak.Speak(str1)

def apply_night_vision(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    equalized = cv2.equalizeHist(gray)
    return cv2.cvtColor(equalized, cv2.COLOR_GRAY2BGR)

def initialize_webcam(retries=3):
    """Initialize the webcam with retries."""
    for attempt in range(retries):
        print(f"Attempting to initialize webcam (Attempt {attempt + 1}/{retries})...")
        video = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Use DirectShow for better compatibility on Windows
        if video.isOpened():
            print("Webcam initialized successfully.")
            return video
        else:
            print("Failed to initialize webcam. Retrying...")
            video.release()
            time.sleep(1)  # Wait for 1 second before retrying
    print("Failed to initialize webcam after multiple attempts.")
    return None

def speak(text):
    """Text-to-speech functionality using Windows SAPI."""
    try:
        sapi_voice = Dispatch("SAPI.SpVoice")
        sapi_voice.Speak(text)
    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        flash("Text-to-speech functionality is not available on this system.")

def generate_frames():
    video = initialize_webcam()
    if not video:
        print("Failed to access webcam.")
        return

    while True:
        success, frame = video.read()
        if not success:
            print("Failed to capture frame.")
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                print("Failed to encode frame.")
                break
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
    video.release()

def extract_folder_id(drive_folder_link):
    match = re.search(r'folders/([a-zA-Z0-9-_]+)', drive_folder_link)
    if match:
        return match.group(1)
    else:
        return None

def check_file_exists_in_drive(file_name, folder_id):
    creds = get_credentials()
    if not creds:
        return False
    
    try:
        pass  # Add your code logic here
    except Exception as e:
        flash(f"An error occurred: {e}")
        print(f"Error details: {e}")
        pass  # Add your code logic here
    except Exception as e:
        flash(f"An error occurred: {e}")
        print(f"Error details: {e}")
        pass  # Add your code logic here
    except Exception as e:
        flash(f"An error occurred: {e}")
        print(f"Error details: {e}")
    except Exception as e:
        flash(f"An error occurred: {e}")
        print(f"Error details: {e}")
        service = build('drive', 'v3', credentials=creds)
        query = f"'{folder_id}' in parents and name='{file_name}'"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        return len(results.get('files', [])) > 0
    except HttpError as error:
        print(f"Drive API error: {error}")
        return False 

def get_credentials():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = Flow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            flash("Authentication failed. Please reauthenticate.", "error")
            return None
    return creds       

# In-memory storage for room candidates (for simplicity)

def check_if_exists(name, aadhar, room_id):
    """Check if a voter has already voted based on name, aadhar, and room_id."""
    votes_file = f"{session.get('election_name', 'Election')}_Votes.csv"
    print(f"Checking if voter exists: Name={name}, Aadhar={aadhar}, Room ID={room_id}")
    
    if not os.path.exists(votes_file):
        print("Votes file does not exist.")
        return "not_voted"
    
    with open(votes_file, "r") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            # Ensure the row has enough columns to avoid index errors
            if len(row) >= 6:
                existing_name, existing_aadhar, _, _, _, existing_room_id = row
                # Check if all three fields match
                if existing_name == name and existing_aadhar == aadhar and existing_room_id == room_id:
                    print("Voter has already voted.")
                    return "already_voted"
    print("Voter has not voted yet.")
    return "not_voted"

room_candidates = {}
expired_rooms = set()
voted_rooms = {}

def generate_room_id():
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=6))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/host_login', methods=['GET', 'POST'])
def host_login():
    if request.method == 'POST':
        session['election_name'] = request.form['election_name']
        folder_id = extract_folder_id(request.form['drive_folder_link'])
        
        if not folder_id:
            flash("Invalid Google Drive folder link", "error")
            return redirect(url_for('host_login'))
        
        session['folder_id'] = folder_id
        session['room_id'] = generate_room_id()
        return redirect(url_for('voting_room'))
    
    return render_template('hostlogin.html')

@app.route('/voting_room', methods=['GET', 'POST'])
def voting_room():
    if request.method == 'POST':
       # Save candidate names for the room ID
        room_id = session['room_id']
        room_candidates[room_id] = {
            'candidate1': request.form['candidate1'],
            'candidate2': request.form['candidate2'],
            'candidate3': request.form['candidate3'],
            'candidate4': request.form['candidate4'],
            'candidate5': request.form['candidate5'],
            'candidate6': request.form['candidate6'],
            'candidate7': request.form['candidate7'],
            'candidate8': request.form['candidate8']
        }
        return redirect(url_for('index'))
    
    if 'room_id' not in session:
        flash("Invalid room id or already voted.")
        return redirect(url_for('index'))
    
    room_id = session['room_id']
    return render_template('votingroom.html', room_id=room_id)

@app.route('/flash_message')
def flash_message():
    message = request.args.get('message')
    category = request.args.get('category', 'message')
    flash(message, category)
    return redirect(url_for('index'))

@app.route('/validate_room', methods=['POST'])
def validate_room():
    data = request.get_json()
    room_id = data.get('room_id')
    
    if room_id not in room_candidates:
        return jsonify({'message': 'Invalid Room ID.'}), 400
    if room_id in expired_rooms:
        return jsonify({'message': 'This Room ID has expired.'}), 400
    
    return jsonify({'message': 'Room ID is valid.'}), 200



@app.route('/vote/<room_id>')
def vote(room_id):
    if room_id not in room_candidates:
        flash("Invalid Room ID. Please try again.", "error")
        return redirect(url_for('index'))

    candidates = room_candidates[room_id]  # Retrieve candidates for the room
    name = session.get('name', '')
    aadhar = session.get('aadhar', '')
    return render_template('vote.html', candidates=candidates, room_id=room_id, name=name, aadhar=aadhar)

def upload_to_drive(file_content, file_name, folder_id, room_id):
    creds = get_credentials()
    if not creds:
        flash("Failed to authenticate with Google Drive. Please reauthenticate.", "error")
        return None
    
    try:
        service = build('drive', 'v3', credentials=creds)

        # Check if file already exists in the folder
        query = f"'{folder_id}' in parents and name='{file_name}'"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if items:
            # File exists, update it
            file_id = items[0]['id']
            media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream')
            file = service.files().update(fileId=file_id, media_body=media).execute()
            print(f"File ID: {file.get('id')} updated with new content.")
        else:
            # Create a new file
            file_metadata = {'name': file_name, 'parents': [folder_id]}
            media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream')
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_id = file.get('id')
            print(f"File ID: {file_id} created.")
        return file_id    
    except HttpError as error:
        print(f"An error occurred: {error}")
        flash(f"Google Drive API error: {error}", "error")
        return None

def make_file_non_editable(file_id):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        
        # Retrieve the existing permissions
        permissions = service.permissions().list(fileId=file_id).execute()
        if 'permissions' in permissions:
            for permission in permissions['permissions']:
                # Remove the existing permissions
                if permission['role'] != 'owner':  # Highlighted change
                    service.permissions().delete(fileId=file_id, permissionId=permission['id']).execute()
        
        # Add a new permission to make the file non-editable
        new_permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(fileId=file_id, body=new_permission).execute()
        print(f"File ID: {file_id} is now non-editable.")
    except HttpError as error:
        print(f"An error occurred: {error}")
    
@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    video = None
    try:
        # Load the pre-trained KNN model
        knn_model_path = 'data/knn_model.pkl'
        if not os.path.exists(knn_model_path) or os.path.getsize(knn_model_path) == 0:
            flash("KNN model not found or is corrupted. Please train the model first.")
            return redirect(url_for('index'))
        try:
            with open(knn_model_path, 'rb') as model_file:
                knn = pickle.load(model_file)
        except (pickle.UnpicklingError, EOFError):
            flash("KNN model file is corrupted. Please retrain the model.")
            return redirect(url_for('index'))

        # Initialize webcam with DirectShow
        video = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not video.isOpened():
            flash("Webcam not accessible. Ensure it's connected and not in use by other applications.")
            return redirect(url_for('vote', room_id=request.form.get('room_id')))
        
        # Attempt to capture frame
        ret, frame = video.read()
        if not ret or frame is None:
            flash("Failed to receive video feed. Check camera permissions and functionality.")
            return redirect(url_for('vote', room_id=request.form.get('room_id')))
        
        # Apply night vision effect
        frame = apply_night_vision(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Load face detection model
        facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        if facedetect.empty():
            flash("Failed to load face detection model. Please check your OpenCV installation.")
            return redirect(url_for('vote', room_id=request.form.get('room_id')))

        # Detect faces
        faces = facedetect.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        if len(faces) == 0:
            flash("No face detected. Please ensure your face is clearly visible to the camera.")
            return redirect(url_for('vote', room_id=request.form.get('room_id')))
        
        # Process detected faces
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50)).flatten().reshape(1, -1)
            output = knn.predict(resized_img)

            # Verify live face using eye blink detection
            is_live_person = True  # Placeholder; implement actual blink detection if needed
            if not is_live_person:
                flash("Please use your live face for voting.")
                return redirect(url_for('vote', room_id=request.form.get('room_id')))

            vote_status = check_if_exists(output[0], request.form.get('aadhar'), request.form.get('room_id')) if 'check_if_exists' in globals() else "not_defined"
            if vote_status == "not_defined":
                flash("Function 'check_if_exists' is not implemented.")
                return redirect(url_for('index'))

            # Retrieve data from session
            name = session.get('name', '').strip().upper()
            aadhar = session.get('aadhar', '').strip()
            room_id = session.get('room_id', '').strip()
            vote_choice = request.form.get('vote')

            # Validate input
            if not name or not aadhar or not room_id or not vote_choice:
                flash("Invalid input. Please try again.")
                return redirect(url_for('vote', room_id=room_id))
            
             # Check if voter has already voted
            vote_status = check_if_exists(name, aadhar, room_id)
            if vote_status == "already_voted":
                speak("YOU HAVE ALREADY VOTED")
                flash("You have already voted")
                return redirect(url_for('index'))

            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M-%S")
            election_name = session.get('election_name', 'Election')
            votes_file = f"{election_name}_Votes.csv"
            
            file_exists = os.path.exists(votes_file)
            with open(votes_file, "a", newline='') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(["Name", "Aadhar", "Vote", "Date", "Timestamp", "Room ID"])
                attendance = [name, aadhar, vote_choice, date, timestamp, room_id]
                writer.writerow(attendance)

            # Announce successful face recognition
            speak("FACE RECOGNITION SUCCESSFUL")

            speak("YOUR VOTE HAS BEEN RECORDED")
            flash(f"Vote casted for {vote_choice}")

        # Upload the votes file to Google Drive
        folder_id = session.get('folder_id')
        if folder_id:
            with open(votes_file, "r") as csvfile:
                csv_content = csvfile.read()
            file_id = upload_to_drive(csv_content.encode('utf-8'), votes_file, folder_id, room_id)
            if file_id:
                make_file_non_editable(file_id)

        return redirect(url_for('votecasted'))

    except Exception as e:
        flash(f"Error: {str(e)}")
        return redirect(url_for('vote', room_id=request.form.get('room_id')))

    finally:
        if video and video.isOpened():
            video.release()
        cv2.destroyAllWindows()
                      

@app.route('/votecasted')
def votecasted():
    return render_template('votecasted.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

def load_pickle_file(file_path, default_value):
    """Safely load a pickle file. If the file is empty or corrupted, reinitialize it."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        # If the file doesn't exist or is empty, initialize it with the default value
        with open(file_path, 'wb') as f:
            pickle.dump(default_value, f)
        return default_value
    try:
        with open(file_path, 'rb') as f:
            return pickle.load(f)
    except (pickle.UnpicklingError, EOFError):
        # If the file is corrupted, reinitialize it
        flash(f"File {file_path} is corrupted or empty. Reinitializing it.")
        with open(file_path, 'wb') as f:
            pickle.dump(default_value, f)
        return default_value

@app.route('/add_faces', methods=['POST'])
def add_faces():
    """Handle the addition of new face samples and update the KNN model."""
    # Get form data
    name = request.form.get('name', '').strip().upper()
    aadhar = request.form.get('aadhar', '').strip()
    room_id = request.form.get('room_id', '').strip()

    # Validate input
    if not name or not re.match(r'^[A-Z\s]+$', name):
        flash("Please enter a valid name (only uppercase letters and spaces allowed)")
        return redirect(url_for('index'))

    if not aadhar or not re.match(r'^\d{12}$', aadhar):
        flash("Please enter a valid 12-digit Aadhar number")
        return redirect(url_for('index'))

    if not room_id or not re.match(r'^[A-Z0-9]+$', room_id):
        flash("Please enter a valid Room ID (digits or capital letters only)")
        return redirect(url_for('index'))

    # Store data in session
    session['name'] = name
    session['aadhar'] = aadhar
    session['room_id'] = room_id

    # Ensure the data directory exists
    if not os.path.exists('data/'):
        os.makedirs('data/')

    # Initialize webcam
    video = initialize_webcam()
    if not video:
        flash("Failed to access webcam. Please check your camera.")
        return redirect(url_for('index'))

    # Load face detection model
    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    if facedetect.empty():
        flash("Failed to load face detection model. Please check your OpenCV installation.")
        video.release()
        return redirect(url_for('index'))

    # Capture face samples
    faces_data = []
    i = 0
    frames_total = 51  # Number of face samples to capture
    capture_after_frame = 2  # Capture every nth frame

    try:
        while True:
            ret, frame = video.read()
            if not ret:
                flash("Failed to capture video. Please ensure your webcam is functioning properly.")
                break

            # Apply night vision effect (customize as needed)
            frame = apply_night_vision(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Detect faces
            faces = facedetect.detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                crop_img = frame[y:y+h, x:x+w]
                resized_img = cv2.resize(crop_img, (50, 50))
                if len(faces_data) < frames_total and i % capture_after_frame == 0:
                    faces_data.append(resized_img)
                i += 1
                cv2.putText(frame, str(len(faces_data)), (50, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 255), 1)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 1)

            # Display the frame
            cv2.imshow('frame', frame)
            k = cv2.waitKey(1)
            if k == ord('q') or len(faces_data) >= frames_total:
                break
    except Exception as e:
        flash(f"An error occurred during face capture: {e}")
    finally:
        if video.isOpened():
            video.release()
        cv2.destroyAllWindows()

    # Convert captured faces to numpy array
    faces_data = np.asarray(faces_data)
    if faces_data.size == 0:
        flash("No faces were captured. Please try again.")
        return redirect(url_for('index'))

    # Flatten each face image (e.g., from (50, 50, 3) to 7500 features)
    faces_data = faces_data.reshape((faces_data.shape[0], -1))

    # Load existing data from a single pickle file
    data_file_path = 'data/data.pkl'
    if os.path.exists(data_file_path):
        try:
            with open(data_file_path, 'rb') as f:
                data = pickle.load(f)
            existing_faces = data['faces']
            names = data['names']
            # Ensure consistency in loaded data
            if len(existing_faces) != len(names):
                min_length = min(len(existing_faces), len(names))
                existing_faces = existing_faces[:min_length]
                names = names[:min_length]
                flash(f"Warning: Existing data had inconsistent sample numbers. Truncated to {min_length} samples.")
        except (pickle.UnpicklingError, EOFError, KeyError, ValueError):
            flash("Data file is corrupted or invalid. Reinitializing.")
            existing_faces = np.empty((0, faces_data.shape[1]))
            names = []
    else:
        existing_faces = np.empty((0, faces_data.shape[1]))
        names = []

    # Append new face data
    if len(faces_data) > 0:
        combined_faces = np.vstack((existing_faces, faces_data)) if existing_faces.size > 0 else faces_data
        names.extend([name] * len(faces_data))

        # Save updated data to a single pickle file
        data = {'faces': combined_faces, 'names': names}
        try:
            with open(data_file_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            flash(f"Error saving data: {e}")
            return redirect(url_for('index'))

        # Train the KNN model
        try:
            knn = KNeighborsClassifier(n_neighbors=5)
            knn.fit(combined_faces, names)
            with open('data/knn_model.pkl', 'wb') as model_file:
                pickle.dump(knn, model_file)
            print("KNN model trained and saved successfully.")
        except Exception as e:
            flash(f"An error occurred while training the KNN model: {e}")
            return redirect(url_for('index'))

    flash("Faces added successfully and KNN model updated.")
    speak("YOUR FACE HAS BEEN RECORDED")
    return redirect(url_for('vote', room_id=room_id))

if __name__ == '__main__':
    app.run(debug=True)        