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

def generate_frames():
    while True:
        success, frame = video.read()
        if not success:
            break
        else:
            frame = apply_night_vision(frame)
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

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
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds       

# In-memory storage for room candidates (for simplicity)
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
    if room_id in voted_rooms:
        return jsonify({'message': 'You have already voted in this Room ID.'}), 400
    
    return jsonify({'message': 'Room ID is valid.'}), 200

@app.route('/expire_room', methods=['POST'])
def expire_room():
    data = request.get_json()
    room_id = data.get('room_id')
    expired_rooms.add(room_id)
    return jsonify({'message': 'Room ID expired.'}), 200

@app.route('/vote/<room_id>')
def vote(room_id):
    if room_id not in room_candidates:
        return redirect(url_for('index'))
    candidates = room_candidates[room_id]
    return render_template('vote.html', candidates=candidates, room_id=room_id)

def upload_to_drive(file_content, file_name, folder_id, room_id):
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

        # Check if file already exists in the folder
        query = f"'{folder_id}' in parents and name='{file_name}' and mimeType='text/csv'"
        results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        items = results.get('files', [])
        
        if items:
            # File exists, append data to it
            file_id = items[0]['id']
            media = MediaIoBaseUpload(io.BytesIO(file_content.encode()), mimetype='text/csv')
            file = service.files().update(fileId=file_id, media_body=media).execute()
            print(f"File ID: {file.get('id')} updated with new content.")
        else:
            # Create a new file
            file_metadata = {'name': file_name, 'parents': [folder_id]}
            media = MediaIoBaseUpload(io.BytesIO(file_content.encode()), mimetype='text/csv')
            file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            file_id = file.get('id')
            print(f"File ID: {file_id} created.")
        return file_id    
    except HttpError as error:
        print(f"An error occurred: {error}")
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
    
@app.route('/cast_vote', methods=['GET', 'POST'])
def cast_vote():
    room_id = request.form.get('room_id')
    voter_id = request.form.get('voter_id')
    aadhar = request.form.get('aadhar')
    vote_choice = request.form['vote']
    video = cv2.VideoCapture(0)
    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    if not facedetect.load(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'):
        flash("Error loading face detection model.")
        return redirect(url_for('vote', room_id=room_id))
    
    elif not os.path.exists('data/'):
          os.makedirs('data/')

    with open('data/names.pkl', 'rb') as f:
        LABELS = pickle.load(f)

    with open('data/faces_data.pkl', 'rb') as f:
        FACES = pickle.load(f)

    min_length = min(len(FACES), len(LABELS))
    FACES = FACES[:min_length]
    LABELS = LABELS[:min_length]

    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(FACES, LABELS)

    COL_NAMES = ['NAME', 'AADHAR', 'VOTE', 'DATE', 'TIME', 'ROOM_ID']

    def check_if_exists(voter_id, aadhar, room_id):
        """Check if the voter has already voted by checking their ID in the 'Votes.csv' file."""
        try:
            election_name = session.get('election_name', 'Election')
            votes_file = f"{election_name}_Votes.csv"
            if not os.path.isfile(votes_file):
                with open(votes_file, "w", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(COL_NAMES)
                return "new_vote"
            with open(votes_file, "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0] == voter_id or row[1] == aadhar:
                        if row[5] == room_id:
                            return "already_voted"
                        else:
                            return "new_room"
        except FileNotFoundError:
            print("File not found or unable to open the CSV file.")
        return "new_vote"

    def detect_eye_blink(frame):
        """Detects eye blinking to verify if the person is live or just a photo."""
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray)
        return len(eyes) > 0  

    try:
        ret, frame = video.read()
        if not ret:
            flash("Failed to capture video. Please ensure your webcam is working.")
            return redirect(url_for('vote', room_id=room_id))

        frame = apply_night_vision(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        faces = facedetect.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))
        if len(faces) == 0:
            flash("No face detected. Please rescan your face.")
            return redirect(url_for('vote', room_id=room_id))

        output = None  
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50)).flatten().reshape(1, -1)
            output = knn.predict(resized_img)

            is_live_person = detect_eye_blink(frame)
            if not is_live_person:
                flash("Please use your live face for voting.")
                return redirect(url_for('vote', room_id=room_id))

            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M-%S")
            election_name = session.get('election_name', 'Election')
            votes_file = f"{election_name}_Votes.csv"
            exist = os.path.isfile(votes_file)

            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 2)
            cv2.rectangle(frame, (x, y-40), (x+w, y), (50, 50, 255), -1)
            cv2.putText(frame, str(output[0]), (x, y-15), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)

            # Zoom in on the face
            zoom_factor = 1.5
            face_center_x, face_center_y = x + w // 2, y + h // 2
            new_w, new_h = int(w * zoom_factor), int(h * zoom_factor)
            start_x, start_y = max(0, face_center_x - new_w // 2), max(0, face_center_y - new_h // 2)
            end_x, end_y = min(frame.shape[1], face_center_x + new_w // 2), min(frame.shape[0], face_center_y + new_h // 2)
            zoomed_face = frame[start_y:end_y, start_x:end_x]
            zoomed_face = cv2.resize(zoomed_face, (frame.shape[1], frame.shape[0]))
            frame = zoomed_face

            speak("FACE RECOGNITION SUCCESSFUL")

        if output is not None:
            vote_status = check_if_exists(output[0], aadhar, room_id)  
            if vote_status == "already_voted":
                speak("YOU HAVE ALREADY VOTED")
                flash("You have already voted")
                return redirect(url_for('index'))
            elif vote_status == "new_room":
                votes_file = f"{election_name}_{room_id}_Votes.csv"
                with open(votes_file, "w", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(COL_NAMES)

            vote_choice = request.form['vote']
            speak("YOUR VOTE HAS BEEN RECORDED")
            time.sleep(5)

            with open(votes_file, "a", newline='') as csvfile:
                writer = csv.writer(csvfile)
                attendance = [output[0], aadhar, vote_choice, date, timestamp, room_id]
                writer.writerow(attendance)

            speak("THANK YOU FOR PARTICIPATING IN THE ELECTIONS")

    except Exception as e:
        flash(f"An error occurred: {e}")
        print(f"Error details: {e}")

    finally:
        video.release()
        cv2.destroyAllWindows()

    folder_id = session.get('folder_id')
    if folder_id:
        with open(votes_file, "r") as csvfile:
            csv_content = csvfile.read()
        file_id = upload_to_drive(csv_content, votes_file, folder_id, room_id)
        make_file_non_editable(file_id)

    flash(f"Vote casted for {vote_choice}") 
    return redirect(url_for('votecasted'))
                      

@app.route('/votecasted')
def votecasted():
    return render_template('votecasted.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/add_faces', methods=['POST'])
def add_faces():
    voter_id = request.form['voter_id']
    aadhar = request.form['aadhar']
    room_id = request.form.get('room_id')

    if not voter_id or not re.match(r'^[A-Z0-9]+$', voter_id):
        flash("Please enter a valid Voter ID (digits or capital letters only)")
        return redirect(url_for('index'))

    if not aadhar or not re.match(r'^\d{12}$', aadhar):
        flash("Please enter a valid 12-digit Aadhar number")
        return redirect(url_for('index'))

    if not os.path.exists('data/'):
        os.makedirs('data/')

    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces_data = []  

    i = 0
    framesTotal = 51
    captureAfterFrame = 2

    try:
        while True:
            ret, frame = video.read()
            if not ret:
                flash("Failed to capture video")
                break
            frame = apply_night_vision(frame)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = facedetect.detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                crop_img = frame[y:y+h, x:x+w]
                resized_img = cv2.resize(crop_img, (50, 50))
                if len(faces_data) <= framesTotal and i % captureAfterFrame == 0:
                    faces_data.append(resized_img)
                i = i + 1
                cv2.putText(frame, str(len(faces_data)), (50, 50), cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 255), 1)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 1)
            cv2.imshow('frame', frame)
            k = cv2.waitKey(1)
            if k == ord('q') or len(faces_data) >= framesTotal:
               break
    except Exception as e:
        flash(f"An error occurred: {e}")

    faces_data = np.asarray(faces_data)
    faces_data = faces_data.reshape((framesTotal, -1))

    if 'names.pkl' not in os.listdir('data/'):
        names = [voter_id] * framesTotal
        with open('data/names.pkl', 'wb') as f:
            pickle.dump(names, f)
    else:
        with open('data/names.pkl', 'rb') as f:
            names = pickle.load(f)
        names = names + [voter_id] * framesTotal
        with open('data/names.pkl', 'wb') as f:
            pickle.dump(names, f)

    if 'faces_data.pkl' not in os.listdir('data/'):
        with open('data/faces_data.pkl', 'wb') as f:
            pickle.dump(faces_data, f)
    else:
        with open('data/faces_data.pkl', 'rb') as f:
            faces = pickle.load(f)
        faces = np.append(faces, faces_data, axis=0)
        with open('data/faces_data.pkl', 'wb') as f:
            pickle.dump(faces, f)   

    flash("Faces added successfully")
    return redirect(url_for('vote', room_id=room_id))

if __name__ == '__main__':
    app.run(debug=True)        