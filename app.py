from flask import Flask, render_template, request, redirect, session, flash, jsonify
import sqlite3
import os
from admin_config import ADMIN_USERNAME, ADMIN_PASSWORD

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hospital.db")


# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            role TEXT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Patients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            firstname TEXT NOT NULL,
            lastname TEXT NOT NULL,
            dob TEXT,
            gender TEXT,
            phone TEXT,
            address TEXT
        )
    ''')

    # Appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_type TEXT NOT NULL,
            patient_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            doctor TEXT NOT NULL,
            time_schedule TEXT NOT NULL,
            issue TEXT NOT NULL,
            blood_group TEXT,
            allergies TEXT,
            medications TEXT,
            notes TEXT,
            previous_appointment_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create default receptionist if not exists
    cursor.execute("SELECT * FROM users WHERE username=?", ("receptionist1",))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users
            (firstname, lastname, email, phone, role, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Reception", "Staff", "reception@hospital.com",
            "9876543210", "Receptionist", "receptionist1", "1234"
        ))

    # Create default doctor if not exists
    cursor.execute("SELECT * FROM users WHERE username=?", ("doctor1",))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users
            (firstname, lastname, email, phone, role, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            "Doctor", "Default", "doctor1@hospital.com",
            "9999999999", "Doctor", "doctor1", "1234"
        ))

    conn.commit()
    conn.close()


init_db()


# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/register')
def register():
    return render_template("register.html")


# ---------------- USER LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            role = user[5]
            if role == 'Administrator':
                session['is_admin'] = True
                return redirect('/admin')
            elif role == 'Receptionist':
                session['is_receptionist'] = True
                return redirect('/receptionist')
            elif role == 'Doctor':
                session['is_doctor'] = True
                return redirect('/doctor')
            return redirect('/')

        return "Invalid Username or Password"

    return render_template("login.html")


# ---------------- ADD USER ----------------
@app.route('/submit-registration', methods=['POST'])
def submit_registration():
    firstname = request.form['firstname']
    lastname  = request.form['lastname']
    email     = request.form['email']
    phone     = request.form['phone']
    role      = request.form['role']
    username  = request.form['username']
    password  = request.form['password']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (firstname, lastname, email, phone, role, username, password)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (firstname, lastname, email, phone, role, username, password))
        conn.commit()
    except sqlite3.IntegrityError:
        return "Username or Email already exists!"
    finally:
        conn.close()

    return redirect('/admin')


# ---------------- ADMIN ----------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect('/admin')
        return render_template('admin_login.html', error='Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('is_admin', None)
    return redirect('/admin/login')

@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect('/admin/login')
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return render_template("admin.html", users=users, users_count=len(users))


# ---------------- DOCTOR ----------------
@app.route('/doctor/login', methods=['GET', 'POST'])
def doctor_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM users WHERE username=? AND password=? AND role=?',
            (username, password, 'Doctor')
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            session['is_doctor'] = True
            # store logged-in doctor identifier for filtering appointments
            # users table columns: id, firstname, lastname, email, phone, role, username, password
            session['doctor_username'] = user[6]
            return redirect('/doctor')

        return render_template('doctor_login.html', error='Invalid Username or Password')

    return render_template('doctor_login.html')


@app.route('/doctor/logout', methods=['POST'])
def doctor_logout():
    session.pop('is_doctor', None)
    return redirect('/')


@app.route('/doctor')
def doctor():
    if not session.get('is_doctor'):
        return redirect('/doctor/login')

    doctor_username = session.get('doctor_username') or ''

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    doctor_display_name = "Doctor"

    if doctor_username:
        cursor.execute(
            '''
            SELECT firstname, lastname
            FROM users
            WHERE username=?
            ''',
            (doctor_username,)
        )
        doc_user = cursor.fetchone()
        if doc_user:
            doctor_display_name = f"{doc_user['firstname']} {doc_user['lastname']}".strip()

        cursor.execute(
            '''
            SELECT * FROM appointments
            WHERE doctor=?
            ORDER BY created_at DESC
            LIMIT 50
            ''',
            (doctor_username,)
        )
    else:
        cursor.execute('SELECT * FROM appointments ORDER BY created_at DESC LIMIT 50')

    appointments = cursor.fetchall()
    conn.close()

    patients = []
    if appointments:
        seen = set()
        for appt in appointments:
            if appt['patient_name'] and appt['patient_name'] not in seen:
                seen.add(appt['patient_name'])
                patients.append({
                    'patient_name': appt['patient_name'],
                    'appointment_type': appt['appointment_type'],
                    'time_schedule': appt['time_schedule'],
                })

    return render_template(
        'doctor_dashboard.html',
        appointments=appointments,
        patients=patients,
        doctor_display_name=doctor_display_name,
        active_page='dashboard'
    )


@app.route('/doctor/patients')
def doctor_patients():
    if not session.get('is_doctor'):
        return redirect('/doctor/login')

    doctor_username = session.get('doctor_username') or ''

    print("[/doctor/patients] is_doctor=True")
    print("[/doctor/patients] session doctor_username =", doctor_username)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    doctor_display_name = "Doctor"
    if doctor_username:
        cursor.execute(
            '''
            SELECT firstname, lastname
            FROM users
            WHERE username=?
            ''',
            (doctor_username,)
        )
        doc_user = cursor.fetchone()
        if doc_user:
            doctor_display_name = f"{doc_user['firstname']} {doc_user['lastname']}".strip()

        cursor.execute(
            '''
            SELECT patient_name, appointment_type, time_schedule
            FROM appointments
            WHERE doctor=?
            ORDER BY created_at DESC
            ''',
            (doctor_username,)
        )
    else:
        cursor.execute(
            '''
            SELECT patient_name, appointment_type, time_schedule
            FROM appointments
            ORDER BY created_at DESC
            '''
        )

    rows = cursor.fetchall()
    print("[/doctor/patients] appointments rows fetched =", len(rows))
    if len(rows) > 0:
        preview = [rows[i]['patient_name'] for i in range(min(5, len(rows)))]
        print("[/doctor/patients] patient_name preview =", preview)

    conn.close()

    patients = []
    seen = set()
    for r in rows:
        if r['patient_name'] and r['patient_name'] not in seen:
            seen.add(r['patient_name'])
            patients.append({
                'patient_name': r['patient_name'],
                'appointment_type': r['appointment_type'],
                'time_schedule': r['time_schedule'],
            })

    print("[/doctor/patients] derived unique patients =", len(patients))
    if len(patients) > 0:
        print("[/doctor/patients] unique patient preview =", [p['patient_name'] for p in patients[:5]])

    return render_template(
        'doctor_dashboard.html',
        appointments=[],
        patients=patients,
        doctor_display_name=doctor_display_name,
        active_page='patients'
    )



# ---------------- DOCTOR: ADD PATIENT ----------------
@app.route('/doctor/add-patient', methods=['POST'])
def doctor_add_patient():
    """
    Called via fetch() from the Add New Patient modal.
    Saves to both `patients` and `appointments` tables,
    then returns JSON so the dashboard row can be added live.
    """
    if not session.get('is_doctor'):
        return jsonify({'status': 'error', 'message': 'Not authenticated'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    # Pull fields
    firstname        = (data.get('firstname') or '').strip()
    lastname         = (data.get('lastname')  or '').strip()
    email            = (data.get('email')     or '').strip()
    phone            = (data.get('phone')     or '').strip()
    dob              = (data.get('dob')       or '').strip()
    gender           = (data.get('gender')    or '').strip()
    address          = (data.get('address')   or '').strip()
    blood_group      = (data.get('blood')     or '').strip()
    appointment_type = (data.get('appointment_type') or '').strip()
    issue            = (data.get('issue')     or '').strip()
    allergies        = (data.get('allergies') or '').strip()
    medications      = (data.get('meds')      or '').strip()
    notes            = (data.get('notes')     or '').strip()
    doctor           = (data.get('doctor')    or '').strip()
    time_schedule    = (data.get('time_schedule') or '').strip()

    # Basic validation
    if not firstname or not lastname:
        return jsonify({'status': 'error', 'message': 'First and last name are required'}), 400
    if not doctor:
        return jsonify({'status': 'error', 'message': 'A doctor must be selected'}), 400
    if not appointment_type:
        return jsonify({'status': 'error', 'message': 'Appointment type is required'}), 400
    if not issue:
        return jsonify({'status': 'error', 'message': 'Health issue is required'}), 400
    if not time_schedule:
        return jsonify({'status': 'error', 'message': 'Schedule date/time is required'}), 400

    patient_name = f"{firstname} {lastname}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # 1. Save to patients table
        cursor.execute(
            '''INSERT INTO patients (firstname, lastname, dob, gender, phone, address)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (firstname, lastname, dob or None, gender or None, phone or None, address or None)
        )

        # 2. Save to appointments table (so it shows on the dashboard after refresh)
        # Store doctor in a consistent identifier for doctor dashboard filtering.
        # Always store `users.username` (e.g. "doctor1") so /doctor dashboard filtering works.
        doctor_identifier = session.get('doctor_username') or doctor

        cursor.execute(
            '''INSERT INTO appointments
               (appointment_type, patient_name, email, phone, doctor,
                time_schedule, issue, blood_group, allergies, medications, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                appointment_type, patient_name,
                email or None, phone or None, doctor_identifier,
                time_schedule, issue,
                blood_group or None, allergies or None,
                medications or None, notes or None
            )
        )

        new_appointment_id = cursor.lastrowid
        conn.commit()

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({'status': 'error', 'message': str(e)}), 500

    conn.close()

    return jsonify({
        'status': 'ok',
        'id': new_appointment_id,
        'patient_name': patient_name,
        'doctor': doctor,
        'appointment_type': appointment_type,
        'time_schedule': time_schedule,
        'issue': issue
    })


# ---------------- RECEPTIONIST ----------------
@app.route('/receptionist/login', methods=['GET', 'POST'])
def receptionist_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM users WHERE username=? AND password=? AND role=?',
            (username, password, 'Receptionist')
        )
        user = cursor.fetchone()
        conn.close()
        if user:
            session['is_receptionist'] = True
            return redirect('/receptionist')
        return render_template('receptionist_login.html', error='Invalid Username or Password')
    return render_template('receptionist_login.html')


@app.route('/receptionist/logout', methods=['POST'])
def receptionist_logout():
    session.pop('is_receptionist', None)
    return redirect('/receptionist/login')

@app.route('/receptionist')
def receptionist():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')
    return redirect('/receptionist/patients')

@app.route('/receptionist/patients')
def receptionist_patients():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM patients ORDER BY id DESC')
    patients = cursor.fetchall()

    cursor.execute('SELECT * FROM users WHERE role=?', ('Receptionist',))
    receptionist_user = cursor.fetchone()
    receptionist_name = (
        f"{receptionist_user['firstname']} {receptionist_user['lastname']}"
        if receptionist_user else 'Receptionist'
    )

    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'receptionist.html',
        receptionist_name=receptionist_name,
        patients=patients,
        users_count=users_count,
        active_page='patients',
    )


@app.route('/receptionist/billing')
def receptionist_billing():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    conn.close()

    return render_template('receptionist_billing.html', users_count=users_count, active_page='billing')


@app.route('/receptionist/payments')
def receptionist_payments():
    return redirect('/receptionist/billing')


@app.route('/receptionist/appointments')
def receptionist_appointments():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]

    cursor.execute('SELECT * FROM appointments ORDER BY created_at DESC')
    appointments = cursor.fetchall()
    conn.close()

    return render_template(
        'receptionist_appointments.html',
        appointments=appointments,
        users_count=users_count,
        active_page='appointments',
    )


@app.route('/receptionist/records')
def receptionist_records():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    conn.close()

    return render_template('receptionist_records.html', users_count=users_count, active_page='records')


@app.route('/receptionist/settings')
def receptionist_settings():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    conn.close()

    return render_template('receptionist_settings.html', users_count=users_count, active_page='settings')


# ---------------- ADD PATIENT (Receptionist) ----------------
@app.route('/receptionist/patients/add', methods=['POST'])
def receptionist_patients_add():
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    firstname = request.form.get('firstname', '').strip()
    lastname  = request.form.get('lastname',  '').strip()
    dob       = request.form.get('dob',       '').strip()
    gender    = request.form.get('gender',    '').strip()
    phone     = request.form.get('phone',     '').strip()
    address   = request.form.get('address',   '').strip()

    if not firstname or not lastname:
        flash("First name and last name are required.", "error")
        return redirect('/receptionist/patients')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO patients (firstname, lastname, dob, gender, phone, address) VALUES (?, ?, ?, ?, ?, ?)',
        (firstname, lastname, dob or None, gender or None, phone or None, address or None)
    )
    conn.commit()
    conn.close()

    flash(f"Patient {firstname} {lastname} added successfully.", "success")
    return redirect('/receptionist/patients')


# ---------------- EDIT PATIENT ----------------
@app.route('/receptionist/patients/edit/<int:patient_id>', methods=['POST'])
def receptionist_patients_edit(patient_id):
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    firstname = request.form.get('firstname', '').strip()
    lastname  = request.form.get('lastname',  '').strip()
    dob       = request.form.get('dob',       '').strip()
    gender    = request.form.get('gender',    '').strip()
    phone     = request.form.get('phone',     '').strip()
    address   = request.form.get('address',   '').strip()

    if not firstname or not lastname:
        flash("First name and last name are required.", "error")
        return redirect('/receptionist/patients')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        '''UPDATE patients
           SET firstname=?, lastname=?, dob=?, gender=?, phone=?, address=?
           WHERE id=?''',
        (firstname, lastname, dob or None, gender or None, phone or None, address or None, patient_id)
    )
    conn.commit()
    conn.close()

    flash("Patient record updated successfully.", "success")
    return redirect('/receptionist/patients')


# ---------------- DELETE PATIENT ----------------
@app.route('/receptionist/patients/delete/<int:patient_id>', methods=['POST'])
def receptionist_patients_delete(patient_id):
    if not session.get('is_receptionist'):
        return redirect('/receptionist/login')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM patients WHERE id=?', (patient_id,))
    conn.commit()
    conn.close()

    flash("Patient deleted successfully.", "success")
    return redirect('/receptionist/patients')


# ---------------- APPOINTMENTS ----------------
@app.route('/appointment', methods=['GET', 'POST'])
def appointment():
    if request.method == 'POST':
        appointment_type = request.form.get('appointment_type', 'new')
        patient_name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        # From dropdown: doctor username (e.g. "doctor1")
        doctor = request.form.get('doctor', '').strip()
        time_schedule = request.form.get('time_schedule', '').strip()
        issue = request.form.get('issue', '').strip()
        previous_appointment_id = request.form.get('previous_appointment_id', '').strip()

        if not appointment_type:
            appointment_type = 'new'

        if appointment_type not in ('new', 'followup'):
            flash('Invalid appointment type.', 'error')
            return redirect('/appointment')

        if not patient_name or not email or not phone or not doctor or not time_schedule or not issue:
            flash('Please fill all required fields.', 'error')
            return redirect('/appointment')

        previous_appointment_id = previous_appointment_id if appointment_type == 'followup' else None

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO appointments (
                appointment_type, patient_name, email, phone, doctor,
                time_schedule, issue, previous_appointment_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (appointment_type, patient_name, email, phone, doctor, time_schedule, issue, previous_appointment_id)
        )
        conn.commit()
        conn.close()

        flash('Appointment submitted successfully.', 'success')
        return redirect('/appointment')

    # GET: fetch doctors for dropdown
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT username, firstname, lastname
        FROM users
        WHERE role=?
        ORDER BY firstname ASC, lastname ASC
        ''',
        ('Doctor',)
    )
    doctors = cursor.fetchall()
    conn.close()

    return render_template('appointment.html', doctors=doctors)


@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/sysreq')
def sysreq():
    return render_template('sysreq.html')

# ---------------- CONTACT ----------------
@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # For now, no persistence layer exists for contact submissions.
        # Validate minimal required fields and show success message.
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        message = (request.form.get('message') or '').strip()

        if not name or not email or not message:
            flash("Please fill all required fields.", "error")
            return redirect('/contact')

        # Optional: basic email sanity check
        if '@' not in email:
            flash("Please enter a valid email address.", "error")
            return redirect('/contact')

        flash("Message received. We’ll contact you shortly.", "success")
        return redirect('/contact?submitted=1')

    return render_template('contact.html')


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)