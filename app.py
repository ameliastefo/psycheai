from flask import Flask, request, flash, render_template, request, jsonify, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, firestore, auth
from werkzeug.security import generate_password_hash, check_password_hash
import os
import google.generativeai as genai
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from firebase_admin import auth
from werkzeug.security import generate_password_hash
import traceback

# Load your Firebase service account key
cred = credentials.Certificate("your-firebase-admin-file.json")  # Ensure this file exists
firebase_admin.initialize_app(cred)
db = firestore.client()



# Load API key from .env file
load_dotenv()

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY")) # Ensure this key is set in your .env file

# Create the model with your specified configurations
generation_config = {
    "temperature": 2,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    system_instruction=" You are a sort of psychologist. You are supposed to chat with people who are struggling emotionally and need support but don't know where to find it. You should advise them to look for a psychologist and open up about their feelings because it is not healthy to struggle on your own. Also, try to make them understand the importance of their life. Try to be as soft and communicable as you can so they feel like they are in a safe space. Give tips and advice on how to deal with different problems like depression, anxiety, panic attacks, etc. Ask them what causes their 'problems'. Try to not make very long answers so the user keeps track of the conversation. You should understand albanian as well as english but your answer should always be in the same language as user's."
)

# Chat history
history = []

# Flask app setup
app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = 'your_secret_key_here'  # Required for session management

# Main page
@app.route('/')
def main():
    title = 'Welcome to Our Website!'
    return render_template('main.html', title=title)

# User interfaces
@app.route('/userhome')
def user_home():
    if 'username' not in session or session.get('role') != 'Patient':
        return redirect(url_for('login'))
    title = 'Welcome to PsycheAI - Patient'
    return render_template('home_user.html', title=title)


@app.route('/user_home')
def user_home1():
    title = 'Welcome to PsycheAI - Patient'
    return render_template('home_user.html', title=title)


@app.route('/aichat')
def aichat():
    title = 'AI Chat'
    return render_template('aichat.html', title=title)

chat_session = model.start_chat(history=[])
# API route to handle user messages for the AI chat
@app.route("/aichat/chat", methods=["POST"])
def aichat_chat():
    user_message = request.json["message"]

    # Maintain chat session
    chat_session = model.start_chat(history=history)
    response = chat_session.send_message(user_message)
    model_response = response.text

    # Append to history
    history.append({"role": "user", "parts": [user_message]})
    history.append({"role": "model", "parts": [model_response]})

    return jsonify({"response": model_response})

@app.route('/psychologists')
def psychologists():
    title = 'Licensed Psychologists'

    # Fetch all public psychologist profiles from Firestore
    docs = db.collection('display').stream()
    psychologists_data = [doc.to_dict() for doc in docs]

    return render_template('psychologists.html', title=title, psychologists=psychologists_data)




@app.route('/book_session', methods=['POST'])
def book_session():
    try:
        data = request.json
        print("Received Data:", data)  # Debugging

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        username = data.get('username')
        booking_date = data.get('booking_date')
        booking_time = data.get('booking_time')
        booking_duration = data.get('booking_duration')

        # Check if any field is missing
        if not all([username, booking_date, booking_time, booking_duration]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Store data in Firestore (auto-generate document ID)
        db.collection('Bookings').add({
            'username': username,
            'date': booking_date,
            'time': booking_time,
            'duration': booking_duration
        })

        return jsonify({'success': True, 'message': 'Booking was done successfully!'}), 200
    except Exception as e:
        print("Error:", str(e))  # Debugging
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/bookings')
def get_bookings():
    date = request.args.get('date')
    docs = db.collection('Bookings').where('date', '==', date).stream()
    bookings = [{
        "username": doc.to_dict()['username'],
        "time": doc.to_dict()['time'],
        "duration": doc.to_dict()['duration']
    } for doc in docs]
    return jsonify({"bookings": bookings})

@app.route('/api/bookings/summary')
def booking_summary():
    docs = db.collection('Bookings').stream()
    summary = {}

    for doc in docs:
        booking = doc.to_dict()
        date = booking['date']
        summary[date] = summary.get(date, 0) + 1

    return jsonify(summary)


@app.route('/api/bookings/month')
def bookings_by_month():
    year = request.args.get('year')
    month = request.args.get('month')

    if not year or not month:
        return jsonify({'error': 'Missing year or month'}), 400

    # Normalize month to two digits
    month = month.zfill(2)

    docs = db.collection('Bookings').stream()
    bookings = {}

    for doc in docs:
        data = doc.to_dict()
        date = data.get('date')  # expected format: YYYY-MM-DD
        if date and date.startswith(f"{year}-{month}"):
            if date not in bookings:
                bookings[date] = []
            bookings[date].append(data)

    return jsonify({'bookings': bookings})


@app.route('/shop')
def shop():
    title = 'Shop'
    return render_template('shop.html', title=title)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        name = data.get('name')
        email = data.get('email')
        username = data.get('username')
        password = data.get('password')

        if not all([name, email, username, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        try:
            print("Creating user in Firebase Auth")
            user_record = auth.create_user(
                email=email,
                password=password,
                display_name=name,
            )
            print("Firebase user created:", user_record.uid)

        except auth.EmailAlreadyExistsError:
            return jsonify({'error': 'Email already exists'}), 400
        except Exception as e:
            print("Error during Firebase Auth creation:")
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

        try:
            hashed_password = generate_password_hash(password)
            print("Hashed password generated")

            if not username:
                print("Error: username is None or empty")
                return jsonify({'error': 'Invalid username'}), 400

            print("Saving user to Firestore with UID:", user_record.uid)
            db.collection('patients').document(user_record.uid).set({
                'uid': user_record.uid,
                'name': name,
                'email': email,
                'username': username,
                'password': hashed_password,
                'role': 'patient'
            })
            print("User saved in Firestore.")

            # ✅ Vendosi këtu pas suksesit
            session['name'] = name
            session['username'] = username

            return jsonify({'message': 'User registered successfully!', 'redirect': '/user_home'}), 200

        except Exception as e:
            print("Error while writing to Firestore:")
            traceback.print_exc()
            return jsonify({'error': 'User created in Auth but failed to save in Firestore', 'details': str(e)}), 500

    return render_template('signup.html')


@app.route('/account')
def account():
    name = session.get('name', 'No Name')
    username = session.get('username', 'No Username')
    return render_template('acc.html', name=name, username=username)

@app.route('/see_more')
def seemore():
    title = 'See more'
    return render_template('seemore.html', title=title)

#Psych interface
@app.route('/psychhome')
def home_psyche():
    if 'username' not in session or session.get('role') != 'Psychologist':
        return redirect(url_for('login'))
    title = 'Welcome to PsycheAI - Psychologist'
    return render_template('home_psych.html', title=title)

@app.route('/psych_home')
def home_psyche1():
    title = 'Welcome to PsycheAI - Psychologist'
    return render_template('home_psych.html', title=title)

@app.route('/messages')
def messages():
    title = 'Start messaging'
    return render_template('messages_user.html', title=title)

@app.route('/messagess')
def messagess():
    title = 'Start messaging'
    return render_template('messages_psyche.html', title=title)

@app.route('/calendar')
def calendar():
    title = 'Calendar'
    return render_template('calendar.html', title=title)

@app.route('/videocall')
def videocall():
    title = 'hello'
    return render_template('pre-videocall.html', title=title)

@app.route('/start_videocall')
def start():
    title = 'Start videocall'
    return render_template('start.html' , title=title)

@app.route('/psychologist_form', methods=['GET', 'POST'])
def psychologist_form():
    if request.method == 'GET':
        return render_template('p_form.html')
    try:
        # Get form data
        username = request.form.get('username')
        email = request.form.get('email')
        full_name = request.form.get('full_name')
        hourly_rate = request.form.get('hourly_rate')
        license_number = request.form.get('license_number')
        address = request.form.get('address')  # Assuming 'address' also contains country info
        university = request.form.get('university')
        specialization = request.form.get('specialization')
        password_plain = request.form.get('password')
        languages = request.form.getlist('language')

        password_hash = generate_password_hash(password_plain)

        # ✅ Handle profile photo
        photo = request.files.get('photo')
        photo_url = ''
        if photo and photo.filename != '':
            filename = secure_filename(photo.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            photo.save(file_path)
            photo_url = f'/static/uploads/{filename}'
        else:
            photo_url = '/static/default.jpg'  # Fallback image

        # 🔍 Check if email already used in Firestore
        existing_user_query = db.collection('psychiatrists').where('email', '==', email).get()
        if existing_user_query:
            return jsonify({'error': 'This email is already registered.'}), 400

        # 🆕 Create user in Firebase Auth
        user_record = auth.create_user(
            email=email,
            email_verified=False,
            password=password_plain,
            display_name=full_name,
            disabled=False
        )

        # 📂 Upload license file
        license_file_url = ''
        license_file = request.files.get('license_file')
        if license_file and license_file.filename != '':
            filename = secure_filename(license_file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            license_file.save(file_path)
            license_file_url = f'/uploads/{filename}'

        # 📝 Save full data to Firestore (admin/private use)
        db.collection('psychiatrists').document(user_record.uid).set({
            'full_name': full_name,
            'hourly_rate': hourly_rate,
            'address': address,
            'license_file': license_file_url,
            'license_number': license_number,
            'email': email,
            'username': username,
            'university': university,
            'password': password_hash,
            'specialization': specialization,
            'uid': user_record.uid
        })

        # 🌍 Save simplified profile to public listing
        db.collection('display').add({
            'name': full_name,
            'specialization': specialization,
            'photo_url': photo_url,
            'country': address,  # If you want to separate country, parse it before this line
            'language': ", ".join(languages),
            'price': float(hourly_rate) if hourly_rate else 0
        })

        # 💾 Store into session (optional but useful)
        session['user_id'] = user_record.uid
        session['full_name'] = full_name
        session['hourly_rate'] = hourly_rate
        session['address'] = address
        session['email'] = email
        session['university'] = university
        session['specialization'] = specialization
        session['languages'] = languages
        session['photo_url'] = photo_url
        session['username'] = username

        return jsonify({'message': 'Form submitted successfully!', 'redirect': '/psych_home'})

    except Exception as e:
        print("🔥 Error in /psychologist_form:", str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/psychologist_acc')
def psychologist_acc():
    full_name = session.get('full_name', 'No Name')
    hourly_rate = session.get('hourly_rate', 'No Price')
    address = session.get('address', 'No Address')
    email = session.get('email', 'No Email')
    university = session.get('university', 'No University')
    specialization = session.get('specialization', 'No Specialization')
    languages = session.get('languages', [])  # it's a list
    photo_url = session.get('photo_url', '/static/default.jpg')  # fallback image

    return render_template('psychologist_acc.html',
                           full_name=full_name,
                           hourly_rate=hourly_rate,
                           address=address,
                           email=email,
                           university=university,
                           specialization=specialization,
                           languages=", ".join(languages),
                           photo_url=photo_url)


@app.route('/psych_join')
def psych_join():
    title = 'Join us'
    return render_template('psych_join.html', title=title)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Get user from Firebase Auth
            user = auth.get_user_by_email(email)
            uid = user.uid
            print(f"✅ Firebase UID: {uid}")

            # Check if user is a psychiatrist
            psychiatrist_query = db.collection('psychiatrists').where('email', '==', email).limit(1).get()
            if psychiatrist_query:
                doc = psychiatrist_query[0]
                data = doc.to_dict()

                # Store all needed fields in session
                session['user_id'] = doc.id
                session['role'] = 'Psychologist'
                session['full_name'] = data.get('full_name', 'No Name')
                session['hourly_rate'] = data.get('hourly_rate', 'No Price')
                session['address'] = data.get('address', 'No Address')
                session['email'] = data.get('email', 'No Email')
                session['university'] = data.get('university', 'No University')
                session['specialization'] = data.get('specialization', 'No Specialization')
                session['languages'] = data.get('language', [])  # Make sure this matches your Firestore field
                session['photo_url'] = data.get('photo_url', '/static/default.jpg')  # Only if saved in Firestore
                session['username'] = data.get('username', 'unknown_user')

                return redirect('/psych_home')

            # Check if user is a patient
            patient_doc = db.collection('patients').document(uid).get()
            if patient_doc.exists:
                data = patient_doc.to_dict()
                session['user_id'] = uid
                session['role'] = 'Patient'
                session['name'] = data.get('name', 'Unknown')
                session['username'] = data.get('username', 'unknown_user')
                return redirect('/user_home')

            return "User not found in any role", 404

        except Exception as e:
            print("❌ Login error:", str(e))
            return "Login failed", 401

    return render_template('login.html')

# Footer
@app.route('/about')
def about():
    title = 'Who we are'
    return render_template('about.html', title=title)

@app.route('/functionality')
def functionality():
    title = 'How it works'
    return render_template('functionality.html', title=title)

@app.route('/reviews')
def reviews():
    title = 'Reviews'
    return render_template('reviews.html', title=title)

@app.route('/support')
def support():
    title = 'Need support?'
    return render_template('support.html', title=title)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
