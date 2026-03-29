from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), 'database.db')

# ── DB INIT ──────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS cases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  TEXT,
            date        TEXT NOT NULL,
            area        TEXT NOT NULL,
            severity    TEXT NOT NULL,
            age_group   TEXT,
            gender      TEXT,
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.commit()
    conn.close()

# ── HELPERS ───────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def row_to_dict(row):
    return dict(row)

# ── ROUTES ────────────────────────────────────────────────────────────────────

# Serve frontend
@app.route('/')
def index():
    return send_from_directory('../frontend', 'index.html')

# Add a single case
@app.route('/api/cases', methods=['POST'])
def add_case():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['date', 'area', 'severity']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO cases (patient_id, date, area, severity, age_group, gender, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        data.get('patient_id', f"PT-{int(datetime.now().timestamp())}"),
        data['date'],
        data['area'],
        data['severity'],
        data.get('age_group', ''),
        data.get('gender', ''),
        data.get('notes', '')
    ))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return jsonify({'message': 'Case added', 'id': new_id}), 201

# Get all cases (with optional filters)
@app.route('/api/cases', methods=['GET'])
def get_cases():
    area      = request.args.get('area')
    severity  = request.args.get('severity')
    date_from = request.args.get('from')
    date_to   = request.args.get('to')

    query = 'SELECT * FROM cases WHERE 1=1'
    params = []

    if area:
        query += ' AND area = ?'; params.append(area)
    if severity:
        query += ' AND severity = ?'; params.append(severity)
    if date_from:
        query += ' AND date >= ?'; params.append(date_from)
    if date_to:
        query += ' AND date <= ?'; params.append(date_to)

    query += ' ORDER BY date DESC'

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])

# Delete a case
@app.route('/api/cases/<int:case_id>', methods=['DELETE'])
def delete_case(case_id):
    conn = get_db()
    conn.execute('DELETE FROM cases WHERE id = ?', (case_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Deleted'})

# Summary stats
@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    total    = conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
    severe   = conn.execute("SELECT COUNT(*) FROM cases WHERE severity='severe'").fetchone()[0]
    zones    = conn.execute('SELECT COUNT(DISTINCT area) FROM cases').fetchone()[0]
    today    = datetime.now().strftime('%Y-%m-%d')
    today_c  = conn.execute('SELECT COUNT(*) FROM cases WHERE date=?', (today,)).fetchone()[0]

    # Hotspots
    hotspots = conn.execute('''
        SELECT area, COUNT(*) as count FROM cases
        GROUP BY area ORDER BY count DESC LIMIT 5
    ''').fetchall()

    # Daily trend (last 30 days)
    trend = conn.execute('''
        SELECT date, COUNT(*) as count FROM cases
        WHERE date >= date('now','-30 days')
        GROUP BY date ORDER BY date
    ''').fetchall()

    conn.close()
    return jsonify({
        'total': total,
        'severe': severe,
        'zones': zones,
        'today': today_c,
        'hotspots': [row_to_dict(r) for r in hotspots],
        'trend': [row_to_dict(r) for r in trend]
    })

# Bulk import cases (CSV-style JSON array)
@app.route('/api/cases/bulk', methods=['POST'])
def bulk_import():
    data = request.get_json()
    if not isinstance(data, list):
        return jsonify({'error': 'Expected a JSON array'}), 400

    conn = get_db()
    added = 0
    for item in data:
        try:
            conn.execute('''
                INSERT INTO cases (patient_id, date, area, severity, age_group, gender, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.get('patient_id', f"PT-BULK-{added}"),
                item['date'], item['area'], item['severity'],
                item.get('age_group',''), item.get('gender',''), item.get('notes','')
            ))
            added += 1
        except Exception:
            continue
    conn.commit()
    conn.close()
    return jsonify({'message': f'{added} cases imported'})

# Seed sample Bengaluru data (for demo/testing)
@app.route('/api/seed', methods=['POST'])
def seed_data():
    import random
    from datetime import timedelta

    areas = ['Rajajinagar','Koramangala','Hebbal','Whitefield','Indiranagar',
             'Jayanagar','Marathahalli','Yelahanka','Banashankari','HSR Layout']
    severities = ['mild','mild','mild','moderate','moderate','severe']
    ages = ['0-12 (Child)','13-25 (Youth)','26-45 (Adult)','46-60 (Middle-aged)','60+ (Senior)']
    genders = ['Male','Female','Other']

    conn = get_db()
    added = 0
    for i in range(30, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        count = random.randint(1, 4) + (3 if i < 7 else 0)
        for j in range(count):
            conn.execute('''
                INSERT INTO cases (patient_id, date, area, severity, age_group, gender, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"PT-SEED-{i}-{j}",
                d,
                random.choice(areas),
                random.choice(severities),
                random.choice(ages),
                random.choice(genders),
                ''
            ))
            added += 1
    conn.commit()
    conn.close()
    return jsonify({'message': f'Seeded {added} sample cases'})


if __name__ == '__main__':
    init_db()
    print("\n🦟 PRISM-H Dengue Dashboard")
    print("   Running at → http://localhost:5001\n")
    app.run(debug=True, port=5001)
