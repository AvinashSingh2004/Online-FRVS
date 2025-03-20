<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Face Recognition Voting System</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background-color: #f0f0f0;
        }
        .container {
            background-color: #fff;
            width: 480px;
            padding: 20px;
            align-content: center;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
        }
        .container h1 {
            margin-bottom: 20px;
        }
        .container form {
            display: flex;
            flex-direction: column;
        }
        .container form input {
            margin-bottom: 10px;
            padding: 10px;
            font-size: 16px;
        }
        .container form button {
            padding: 10px;
            font-size: 16px;
            background-color: #007BFF;
            color: #fff;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        .container form button:hover {
            background-color: #0056b3;
        }
        .messages {
            margin-bottom: 20px;
            color: red;
        }
        .video-container {
            margin-bottom: 20px;
            display: flex;
            justify-content: center;
        }
        .check-icon {
                margin-top: 20px;
            margin-bottom: 20px;
           width: 120px;
           height: 120px;
           text-align: center;
            color: green;
            font-size: 60px;
            border: 4px solid green;
            border-radius: 80px;
            padding: 5px;
            display: none;
            justify-content: center;
            align-items: center;
            margin: 0 auto;
        }
        .success-message {
            display: none;
            color: rgb(1, 102, 1);
            text-align: center;
            margin-bottom: 20px;
            font-size: 18px;
            margin-top: 10px;
        }
    </style>
    <script>
        function validateForm() {
            const aadhar = document.getElementById('aadhar').value;
            const voterId = document.getElementById('voter_id').value;
            const aadharPattern = /^\d{12}$/;
            const voterIdPattern = /^[A-Z0-9]+$/;

            if (!aadharPattern.test(aadhar)) {
                alert('Please enter a valid 12-digit Aadhar number');
                return false;
            }

            if (!voterIdPattern.test(voterId)) {
                alert('Please enter a valid Voter ID (digits or capital letters only)');
                return false;
            }

            return true;
        }

        function showCheckIcon() {
            document.querySelector('.video-container').style.display = 'none';
            document.querySelector('.check-icon').style.display = 'flex';
            document.querySelector('.success-message').style.display = 'block';
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>Face Recognition Voting System</h1>
        <div class="messages">
            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    {% for message in messages %}
                        <p>{{ message }}</p>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>
        <div class="video-container">
            <img src="{{ url_for('video_feed') }}" width="480" height="360">
        </div>
        <div class="check-icon">
                <i class="fas fa-check"></i>
            </div>
            <div class="success-message">
                Face added successfully!
            </div>
        <form action="/add_faces" method="post" onsubmit="return validateForm()">
            <input type="text" id="voter_id" name="voter_id" placeholder="Enter your Voter ID" required>
            <input type="text" id="aadhar" name="aadhar" placeholder="Enter your Aadhar number" required>
            <button type="submit" onclick="showCheckIcon()">Add Faces</button>
        </form>
    </div>
</body>
</html>





.check-icon {
                margin-top: 20px;
            margin-bottom: 20px;
           width: 120px;
           height: 120px;
           text-align: center;
            color: green;
            font-size: 60px;
            border: 4px solid green;
            border-radius: 80px;
            padding: 5px;
            display: none;
            justify-content: center;
            align-items: center;
            margin: 0 auto;
        }




        from flask import Flask, render_template, request, redirect, url_for, flash, Response
import cv2
import pickle
import numpy as np
import os
import csv
import time
from datetime import datetime
from sklearn.neighbors import KNeighborsClassifier
from win32com.client import Dispatch
import re

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/add_faces', methods=['POST'])
def add_faces():
    voter_id = request.form['voter_id']
    aadhar = request.form['aadhar']
    
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
    return redirect(url_for('vote'))

@app.route('/vote')
def vote():
    return render_template('vote.html')

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    with open('data/names.pkl', 'rb') as f:
        LABELS = pickle.load(f)

    with open('data/faces_data.pkl', 'rb') as f:
        FACES = pickle.load(f)

    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(FACES, LABELS)

    COL_NAMES = ['NAME', 'VOTE', 'DATE', 'TIME']

    def check_if_exists(value):
        try:
            with open("Votes.csv", "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0] == value:
                        return True
        except FileNotFoundError:
            print("File not found or unable to open the CSV file.")
        return False

    try:
        ret, frame = video.read()
        if not ret:
            flash("Failed to capture video")
            return redirect(url_for('vote'))
        
        frame = apply_night_vision(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = facedetect.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            flash("Failed to detect the face, please retry.")
            return redirect(url_for('vote'))
        
        output = None  # Initialize output to a default value
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50)).flatten().reshape(1, -1)
            output = knn.predict(resized_img)
            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M-%S")
            exist = os.path.isfile("Votes.csv")
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 2)
            cv2.rectangle(frame, (x, y-40), (x+w, y), (50, 50, 255), -1)
            cv2.putText(frame, str(output[0]), (x, y-15), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 1)
            attendance = [output[0], timestamp]
        
        if output is not None:
            voter_exist = check_if_exists(output[0])
            if voter_exist:
                speak("YOU HAVE ALREADY VOTED")
                flash("You have already voted")
                return redirect(url_for('vote'))

            vote_choice = request.form['vote']
            speak("YOUR VOTE HAS BEEN RECORDED")
            time.sleep(5)
            if exist:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)
            else:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(COL_NAMES)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)
            speak("THANK YOU FOR PARTICIPATING IN THE ELECTIONS")
            flash("Vote casted successfully")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)











































    from flask import Flask, render_template, request, redirect, url_for, flash, Response
import cv2
import pickle
import numpy as np
import os
import csv
import time
from datetime import datetime
from sklearn.neighbors import KNeighborsClassifier
from win32com.client import Dispatch
import re

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/add_faces', methods=['POST'])
def add_faces():
    voter_id = request.form['voter_id']
    aadhar = request.form['aadhar']
    
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

    # Update faces and labels
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
    return redirect(url_for('vote'))

@app.route('/vote')
def vote():
    return render_template('vote.html')
@app.route('/votecasted')
def votecasted():
    return render_template('votecasted.html')
@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    with open('data/names.pkl', 'rb') as f:
        LABELS = pickle.load(f)

    with open('data/faces_data.pkl', 'rb') as f:
        FACES = pickle.load(f)

    # Ensure that FACES and LABELS have the same length
    min_length = min(len(FACES), len(LABELS))
    FACES = FACES[:min_length]
    LABELS = LABELS[:min_length]

    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(FACES, LABELS)

    COL_NAMES = ['NAME', 'VOTE', 'DATE', 'TIME']

    def check_if_exists(value):
        try:
            with open("Votes.csv", "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0] == value:
                        return True
        except FileNotFoundError:
            print("File not found or unable to open the CSV file.")
        return False

    try:
        ret, frame = video.read()
        if not ret:
            flash("Failed to capture video")
            return redirect(url_for('vote'))
        
        frame = apply_night_vision(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = facedetect.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            flash("Failed to detect the face, please retry.")
            return redirect(url_for('vote'))
        
        output = None  # Initialize output to a default value
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50)).flatten().reshape(1, -1)
            output = knn.predict(resized_img)
            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M-%S")
            exist = os.path.isfile("Votes.csv")
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 2)
            cv2.rectangle(frame, (x, y-40), (x+w, y), (50, 50, 255), -1)
            cv2.putText(frame, str(output[0]), (x, y-15), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)
            attendance = [output[0], timestamp]
        
        if output is not None:
            voter_exist = check_if_exists(output[0])
            if voter_exist:
                speak("YOU HAVE ALREADY VOTED")
                flash("You have already voted")
                return redirect(url_for('vote'))

            vote_choice = request.form['vote']
            speak("YOUR VOTE HAS BEEN RECORDED")
            time.sleep(5)
            if exist:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)
            else:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(COL_NAMES)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)
            speak("THANK YOU FOR PARTICIPATING IN THE ELECTIONS")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return redirect(url_for('votecasted'))

if __name__ == '__main__':
    app.run(debug=True)


EJCGFO

 election_name = session.get('election_name', 'Election')
            votes_file = f"{election_name}_Votes.csv"


@app.route('/vote/<room_id>')
def vote(room_id):
    if room_id not in room_candidates:
        return redirect(url_for('index'))
    candidates = room_candidates[room_id]
    return render_template('vote.html', candidates=candidates, room_id=room_id)

    csv_content = io.StringIO()
            writer = csv.writer(csv_content)
            if exist:
                with open(votes_file, "r") as csvfile:
                    reader = csv.reader(csvfile)
                    for row in reader:
                            writer.writerow(row)
            else:
                writer.writerow(COL_NAMES)
            attendance = [output[0], aadhar, vote_choice, date, timestamp, room_id]
            writer.writerow(attendance)

             # Save the CSV content to the file
            with open(votes_file, "w", newline='') as csvfile:
                csvfile.write(csv_content.getvalue())   






# Save faces_data to a pickle file
    faces_data_pickle = pickle.dumps(faces_data)

    # Upload faces_data.pkl to Google Drive
    file_name = f"{election_name}_{room_id}_faces_data.pkl"
    upload_success = upload_to_drive(faces_data_pickle, file_name, folder_id)

    # Check existence in Drive
    try:
        if upload_success and check_file_exists_in_drive(file_name, folder_id):
            flash("Face data uploaded successfully")
            return redirect(url_for('vote', room_id=room_id))
        else:
            flash("Failed to verify face data upload")
            return redirect(url_for('index'))
    except Exception as e:
        flash(f"Face capture error: {str(e)}")
        return redirect(url_for('index'))


def upload_to_drive(file_content, file_name, folder_id):
    creds = get_credentials()
    if not creds:
        return None

    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': file_name, 'parents': [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='application/octet-stream')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        make_file_non_editable(file.get('id'))
        return file.get('id')
    except HttpError as error:
        print(f"Drive upload error: {error}")
        return None


def make_file_non_editable(file_id):
    creds = get_credentials()
    if not creds:
        return

    try:
        service = build('drive', 'v3', credentials=creds)
        service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
    except HttpError as error:
        print(f"Permission error: {error}")   
























    from flask import Flask, render_template, request, redirect, url_for, flash, Response
import cv2
import pickle
import numpy as np
import os
import csv
import time
from datetime import datetime
from sklearn.neighbors import KNeighborsClassifier
from win32com.client import Dispatch
import re

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flashing messages

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/add_faces', methods=['POST'])
def add_faces():
    voter_id = request.form['voter_id']
    aadhar = request.form['aadhar']
    
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

    # Update faces and labels
    if 'names.pkl' not in os.listdir('data/'):
        names = [voter_id] * framesTotal
        with open('data/names.pkl', 'wb') as f:
            pickle.dump(names, f)
    else:
        with open('data/names.pkl', 'rb') as f:
            names = pickle.load(f)
        # Instead of adding multiple IDs, replace the old ones with the latest `voter_id`
        names = [voter_id] * framesTotal  # Use only the latest voter ID
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

    flash("Faces recorded successfully")
    speak("YOUR FACE HAS BEEN SCANNED")
    return redirect(url_for('vote'))

@app.route('/vote')
def vote():
    return render_template('vote.html')

@app.route('/votecasted')
def votecasted():
    return render_template('votecasted.html')

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    facedetect = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    if not facedetect.load(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'):
        flash("Error loading face detection model.")
        return redirect(url_for('vote'))

    with open('data/names.pkl', 'rb') as f:
        LABELS = pickle.load(f)

    with open('data/faces_data.pkl', 'rb') as f:
        FACES = pickle.load(f)

    # Ensure that FACES and LABELS have the same length
    min_length = min(len(FACES), len(LABELS))
    FACES = FACES[:min_length]
    LABELS = LABELS[:min_length]

    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(FACES, LABELS)

    COL_NAMES = ['NAME', 'VOTE', 'DATE', 'TIME']

    def check_if_exists(value):
        """Check if the voter has already voted by checking their ID in the 'Votes.csv' file."""
        try:
            with open("Votes.csv", "r") as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if row and row[0] == value:  # Match by voter ID
                        return True
        except FileNotFoundError:
            print("File not found or unable to open the CSV file.")
        return False

    def detect_eye_blink(frame):
        """Detects eye blinking to verify if the person is live or just a photo."""
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        eyes = eye_cascade.detectMultiScale(gray)
        return len(eyes) > 0  # If eyes detected, it's likely not a photo

    try:
        ret, frame = video.read()
        if not ret:
            flash("Failed to capture video")
            return redirect(url_for('vote'))
        
        frame = apply_night_vision(frame)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Detect faces in the frame
        faces = facedetect.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))

        if len(faces) == 0:
            flash("No face detected. Please rescan your face.")
            return redirect(url_for('vote'))

        output = None  # Initialize output to a default value
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50)).flatten().reshape(1, -1)
            output = knn.predict(resized_img)

            # Check for eye blink to detect if it's a live person or a photo
            is_live_person = detect_eye_blink(frame)
            if not is_live_person:
                flash("Please use your live face for voting.")
                return redirect(url_for('vote'))

            # If a face is detected and it's a live person, proceed
            ts = time.time()
            date = datetime.fromtimestamp(ts).strftime("%d-%m-%Y")
            timestamp = datetime.fromtimestamp(ts).strftime("%H:%M-%S")
            exist = os.path.isfile("Votes.csv")
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 2)
            cv2.rectangle(frame, (x, y-40), (x+w, y), (50, 50, 255), -1)
            cv2.putText(frame, str(output[0]), (x, y-15), cv2.FONT_HERSHEY_COMPLEX, 1, (255, 255, 255), 1)

        if output is not None:
            voter_exist = check_if_exists(output[0])  # Check if this voter already voted
            if voter_exist:
                speak("YOU HAVE ALREADY VOTED")
                flash("You have already voted")
                return redirect(url_for('vote'))

            vote_choice = request.form['vote']
            speak("YOUR VOTE HAS BEEN RECORDED")
            time.sleep(5)
            
            # Record the vote in the CSV file
            if exist:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)
            else:
                with open("Votes.csv", "a", newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(COL_NAMES)
                    attendance = [output[0], vote_choice, date, timestamp]
                    writer.writerow(attendance)

            speak("THANK YOU FOR PARTICIPATING IN THE ELECTIONS")
    except Exception as e:
        flash(f"An error occurred: {e}")

    return redirect(url_for('votecasted'))



if __name__ == '__main__':
    app.run(debug=True)
