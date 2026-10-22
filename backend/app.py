from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import io
from datetime import datetime, timedelta
from fpdf import FPDF

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
    q         = request.args.get('q', '').strip()

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
    if q:
        query += ''' AND (
            patient_id LIKE ? OR
            area LIKE ? OR
            notes LIKE ? OR
            severity LIKE ? OR
            age_group LIKE ? OR
            gender LIKE ?
        )'''
        q_param = f'%{q}%'
        params.extend([q_param, q_param, q_param, q_param, q_param, q_param])

    query += ' ORDER BY date DESC'

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])

# Quick patient search across all records by name/ID/area
@app.route('/api/cases/search', methods=['GET'])
def search_cases():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    limit = request.args.get('limit', 20, type=int)
    conn = get_db()
    q_param = f'%{q}%'
    rows = conn.execute('''
        SELECT * FROM cases
        WHERE patient_id LIKE ? OR area LIKE ? OR notes LIKE ? OR severity LIKE ? OR age_group LIKE ? OR gender LIKE ?
        ORDER BY date DESC
        LIMIT ?
    ''', (q_param, q_param, q_param, q_param, q_param, q_param, limit)).fetchall()
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

# Update (edit) an existing case
@app.route('/api/cases/<int:case_id>', methods=['PUT'])
def update_case(case_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    required = ['date', 'area', 'severity']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing field: {field}'}), 400

    conn = get_db()
    # Check if case exists
    existing = conn.execute('SELECT id FROM cases WHERE id = ?', (case_id,)).fetchone()
    if not existing:
        conn.close()
        return jsonify({'error': 'Case not found'}), 404

    conn.execute('''
        UPDATE cases
        SET patient_id = ?, date = ?, area = ?, severity = ?, age_group = ?, gender = ?, notes = ?
        WHERE id = ?
    ''', (
        data.get('patient_id', ''),
        data['date'],
        data['area'],
        data['severity'],
        data.get('age_group', ''),
        data.get('gender', ''),
        data.get('notes', ''),
        case_id
    ))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Case updated', 'id': case_id})

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
    trend_rows = conn.execute('''
        SELECT date, COUNT(*) as count FROM cases
        WHERE date >= date('now','-30 days')
        GROUP BY date ORDER BY date
    ''').fetchall()

    import random
    trend = []
    for r in trend_rows:
        rd = dict(row_to_dict(r))
        random.seed(rd['date'])
        # Generate mock weather data based on date
        rd['rainfall'] = round(random.uniform(0, 60), 1)  # 0 to 60 mm
        rd['temperature'] = round(random.uniform(22, 35), 1) # 22 to 35 C
        trend.append(rd)

    conn.close()
    return jsonify({
        'total': total,
        'severe': severe,
        'zones': zones,
        'today': today_c,
        'hotspots': [row_to_dict(r) for r in hotspots],
        'trend': trend
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

# ── PDF REPORT GENERATION ────────────────────────────────────────────────────
class DengueReport(FPDF):
    def header(self):
        # Dark header bar
        self.set_fill_color(13, 24, 33)
        self.rect(0, 0, 210, 28, 'F')
        # Accent line
        self.set_fill_color(255, 68, 68)
        self.rect(0, 28, 210, 1.5, 'F')
        # Title
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(232, 244, 248)
        self.set_y(6)
        self.cell(0, 8, '  PRISM-H Dengue Surveillance Report', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', '', 8)
        self.set_text_color(90, 122, 138)
        self.cell(0, 5, f'  Generated: {datetime.now().strftime("%d %b %Y, %I:%M %p")}  |  Bengaluru Region', new_x='LMARGIN', new_y='NEXT')
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(90, 122, 138)
        self.cell(0, 10, f'PRISM-H Dengue Dashboard  |  Page {self.page_no()}/{{nb}}  |  Confidential', align='C')

    def section_title(self, title, r=0, g=212, b=255):
        self.set_fill_color(r, g, b)
        self.rect(10, self.get_y(), 3, 8, 'F')
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(30, 30, 30)
        self.cell(6)
        self.cell(0, 8, title, new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    def stat_box(self, label, value, x, y, w=42, accent=(0, 212, 255)):
        self.set_fill_color(245, 248, 250)
        self.rect(x, y, w, 22, 'F')
        self.set_fill_color(*accent)
        self.rect(x, y, w, 2, 'F')
        self.set_xy(x, y + 4)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(90, 122, 138)
        self.cell(w, 4, label, align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_xy(x, y + 9)
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(*accent)
        self.cell(w, 10, str(value), align='C', new_x='LMARGIN', new_y='NEXT')


@app.route('/api/report', methods=['GET'])
def generate_report():
    conn = get_db()

    # Gather stats
    total = conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0]
    severe = conn.execute("SELECT COUNT(*) FROM cases WHERE severity='severe'").fetchone()[0]
    moderate = conn.execute("SELECT COUNT(*) FROM cases WHERE severity='moderate'").fetchone()[0]
    mild = conn.execute("SELECT COUNT(*) FROM cases WHERE severity='mild'").fetchone()[0]
    zones = conn.execute('SELECT COUNT(DISTINCT area) FROM cases').fetchone()[0]
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_count = conn.execute('SELECT COUNT(*) FROM cases WHERE date=?', (today_str,)).fetchone()[0]

    # Hotspots
    hotspots = conn.execute('''
        SELECT area, COUNT(*) as count FROM cases
        GROUP BY area ORDER BY count DESC LIMIT 10
    ''').fetchall()

    # Recent cases (last 25)
    recent = conn.execute('''
        SELECT id, patient_id, date, area, severity, age_group, gender, notes
        FROM cases ORDER BY date DESC, id DESC LIMIT 25
    ''').fetchall()

    # Trend: last 7 days
    cutoff_7 = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    last_7 = conn.execute('SELECT COUNT(*) FROM cases WHERE date >= ?', (cutoff_7,)).fetchone()[0]
    cutoff_prev7 = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
    prev_7 = conn.execute('SELECT COUNT(*) FROM cases WHERE date >= ? AND date < ?', (cutoff_prev7, cutoff_7)).fetchone()[0]

    # Outbreak risk
    cutoff_3 = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
    last_3 = conn.execute('SELECT COUNT(*) FROM cases WHERE date >= ?', (cutoff_3,)).fetchone()[0]
    avg_3 = last_3 / 3 if last_3 else 0
    avg_7 = last_7 / 7 if last_7 else 0
    trend_val = avg_3 - avg_7
    risk = 'HIGH' if avg_3 >= 8 or trend_val > 3 else 'MEDIUM' if avg_3 >= 4 or trend_val > 1 else 'LOW'

    conn.close()

    # ── BUILD PDF ─────────────────────────────────────────────────────────────
    pdf = DengueReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── SUMMARY STATS ─────────────────────────────────────────────────────────
    pdf.section_title('Summary Statistics')
    y = pdf.get_y()
    pdf.stat_box('TOTAL CASES', total, 12, y, 42, (0, 150, 200))
    pdf.stat_box('SEVERE', severe, 58, y, 42, (255, 68, 68))
    pdf.stat_box('MODERATE', moderate, 104, y, 42, (255, 170, 0))
    pdf.stat_box('ACTIVE ZONES', zones, 150, y, 42, (255, 136, 0))
    pdf.set_y(y + 28)

    # Weekly comparison
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(60, 60, 60)
    change = last_7 - prev_7
    arrow = '+' if change >= 0 else ''
    pdf.cell(0, 6, f'Last 7 days: {last_7} cases  |  Previous 7 days: {prev_7} cases  |  Change: {arrow}{change}', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 6, f'Today\'s cases: {today_count}  |  Mild: {mild}  |  Moderate: {moderate}  |  Severe: {severe}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # ── OUTBREAK RISK ─────────────────────────────────────────────────────────
    pdf.section_title('Outbreak Risk Assessment', 255, 68, 68)
    risk_colors = {'HIGH': (255, 50, 50), 'MEDIUM': (255, 170, 0), 'LOW': (0, 200, 100)}
    rc = risk_colors.get(risk, (100, 100, 100))
    pdf.set_fill_color(rc[0], rc[1], rc[2])
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(50, 10, f'  RISK: {risk}', fill=True, new_x='END')
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 10, f'   3-day avg: {avg_3:.1f}/day  |  7-day avg: {avg_7:.1f}/day  |  Trend: {trend_val:+.1f}/day', new_x='LMARGIN', new_y='NEXT')
    risk_notes = {
        'HIGH': 'Cases rising rapidly. Immediate intervention recommended.',
        'MEDIUM': 'Moderate spread detected. Enhanced surveillance recommended.',
        'LOW': 'Situation under control. Continue routine monitoring.'
    }
    pdf.set_font('Helvetica', 'I', 8)
    pdf.set_text_color(90, 90, 90)
    pdf.cell(0, 6, f'Assessment: {risk_notes[risk]}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)

    # ── HOTSPOT TABLE ─────────────────────────────────────────────────────────
    pdf.section_title('Top Hotspot Zones', 255, 136, 0)
    # Table header
    pdf.set_fill_color(13, 24, 33)
    pdf.set_text_color(232, 244, 248)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.cell(10, 7, '#', border=0, fill=True, align='C', new_x='END')
    pdf.cell(70, 7, 'AREA', border=0, fill=True, new_x='END')
    pdf.cell(30, 7, 'CASES', border=0, fill=True, align='C', new_x='END')
    pdf.cell(50, 7, 'SHARE', border=0, fill=True, align='C', new_x='END')
    pdf.cell(30, 7, 'STATUS', border=0, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
    # Table rows
    pdf.set_font('Helvetica', '', 8)
    for i, h in enumerate(hotspots):
        area_name = h['area']
        count = h['count']
        share = f'{(count / total * 100):.1f}%' if total else '0%'
        status = 'CRITICAL' if count > 10 else 'WARNING' if count > 5 else 'NORMAL'
        if i % 2 == 0:
            pdf.set_fill_color(245, 248, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(10, 6, str(i + 1), border=0, fill=True, align='C', new_x='END')
        pdf.cell(70, 6, area_name, border=0, fill=True, new_x='END')
        pdf.cell(30, 6, str(count), border=0, fill=True, align='C', new_x='END')
        pdf.cell(50, 6, share, border=0, fill=True, align='C', new_x='END')
        sc = (255, 50, 50) if status == 'CRITICAL' else (255, 170, 0) if status == 'WARNING' else (0, 180, 80)
        pdf.set_text_color(*sc)
        pdf.set_font('Helvetica', 'B', 7)
        pdf.cell(30, 6, status, border=0, fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('Helvetica', '', 8)
    pdf.ln(5)

    # ── RECENT CASES TABLE ────────────────────────────────────────────────────
    pdf.section_title('Recent Cases (Last 25)', 0, 212, 255)
    pdf.set_fill_color(13, 24, 33)
    pdf.set_text_color(232, 244, 248)
    pdf.set_font('Helvetica', 'B', 7)
    cols = [('ID', 12), ('DATE', 24), ('PATIENT', 28), ('AREA', 32), ('SEVERITY', 22), ('AGE', 28), ('GENDER', 18), ('NOTES', 26)]
    for label, w in cols:
        pdf.cell(w, 7, label, border=0, fill=True, align='C', new_x='END')
    pdf.ln()
    pdf.set_font('Helvetica', '', 7)
    sev_colors = {'severe': (255, 68, 68), 'moderate': (255, 170, 0), 'mild': (0, 180, 100)}
    for i, r in enumerate(recent):
        if i % 2 == 0:
            pdf.set_fill_color(245, 248, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_text_color(40, 40, 40)
        row_data = [
            (str(r['id']), 12),
            (r['date'] or '', 24),
            (str(r['patient_id'] or '')[:12], 28),
            (str(r['area'] or '')[:14], 32),
            (r['severity'] or '', 22),
            (str(r['age_group'] or '')[:12], 28),
            (r['gender'] or '', 18),
            (str(r['notes'] or '')[:14], 26)
        ]
        for j, (val, w) in enumerate(row_data):
            if j == 4:  # Severity column
                sc = sev_colors.get(val, (40, 40, 40))
                pdf.set_text_color(*sc)
                pdf.set_font('Helvetica', 'B', 7)
                pdf.cell(w, 5.5, val.upper(), border=0, fill=True, align='C', new_x='END')
                pdf.set_font('Helvetica', '', 7)
                pdf.set_text_color(40, 40, 40)
            else:
                pdf.cell(w, 5.5, val, border=0, fill=True, align='C', new_x='END')
        pdf.ln()
    pdf.ln(5)

    # ── FOOTER NOTE ───────────────────────────────────────────────────────────
    pdf.set_font('Helvetica', 'I', 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, 'This report is auto-generated by PRISM-H Dengue Surveillance System. Not for clinical diagnosis.', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 5, f'Data as of {datetime.now().strftime("%d %b %Y %H:%M:%S")}. ML predictions use linear extrapolation on 30-day rolling window.', new_x='LMARGIN', new_y='NEXT')

    # Output
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    filename = f'PRISM-H_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf'
    return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=filename)


if __name__ == '__main__':
    init_db()
    print("\n🦟 PRISM-H Dengue Dashboard")
    print("   Running at → http://localhost:5001\n")
    app.run(debug=True, port=5001)
