from flask import Flask, render_template, request, jsonify, session, send_file
import sqlite3
import os
from datetime import date
from functools import wraps
import io
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'wt_xK9mP_2026_secret')

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri='memory://',
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'workouts.db')

EXERCISES = {
    'A': [
        'Жим гантелей на наклонной скамье от груди',
        'Тяга штанги к животу в наклоне обратным хватом',
        'Разведение гантелей на плечи',
        'Пулловер с одной гантелью лёжа поперёк скамьи',
        'Приседания с одной гантелью у груди',
        'Румынская тяга со штангой до колен',
    ],
    'B': [
        'Жим на трицепс на брусьях',
        'Тяга на кроссовере одной рукой сверху',
        'Отведение одной рукой на плечо',
        'Подъём штанги на бицепс',
        'Зашагивание назад с гантелями на одной ноге',
        'Сгибание ног в тренажёре на бицепс бедра',
    ]
}

# Reference: week starting Monday March 2, 2026
# Parity 0 (even): Mon=A, Wed=B, Fri=A
# Parity 1 (odd):  Mon=B, Wed=A, Fri=B
# Friday March 7, 2026 = workout A  ✓
REFERENCE_MONDAY = date(2026, 3, 2)


def get_suggested_workout(d: date):
    weekday = d.weekday()  # 0=Mon, 2=Wed, 4=Fri
    if weekday not in (0, 2, 4):
        return None
    days_since_ref = (d - REFERENCE_MONDAY).days
    parity = (days_since_ref // 7) % 2  # Python % always non-negative
    if parity == 0:
        return 'A' if weekday in (0, 4) else 'B'
    else:
        return 'B' if weekday in (0, 4) else 'A'


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT    NOT NULL,
            workout_type  TEXT    NOT NULL,
            UNIQUE(date, workout_type)
        );
        CREATE TABLE IF NOT EXISTS exercise_sets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    INTEGER NOT NULL,
            exercise_num  INTEGER NOT NULL,
            exercise_name TEXT    NOT NULL,
            set_num       INTEGER NOT NULL,
            weight        INTEGER,
            reps          INTEGER,
            saved_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES workout_sessions(id),
            UNIQUE(session_id, exercise_num, set_num)
        );
    ''')
    conn.commit()
    conn.close()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/login', methods=['POST'])
@limiter.limit('5 per minute')
def login():
    if request.json.get('password') == '1732':
        session['authenticated'] = True
        return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Неверный пароль'}), 401


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'ok': False, 'error': 'Слишком много попыток. Подождите минуту.'}), 429


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/suggest')
@auth_required
def suggest():
    d_str = request.args.get('date', date.today().isoformat())
    try:
        d = date.fromisoformat(d_str)
    except ValueError:
        return jsonify({'suggested': None})
    return jsonify({'suggested': get_suggested_workout(d)})


@app.route('/api/session', methods=['POST'])
@auth_required
def get_or_create_session():
    data = request.json
    workout_date = data['date']
    workout_type = data['type']

    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(
            'INSERT OR IGNORE INTO workout_sessions (date, workout_type) VALUES (?, ?)',
            (workout_date, workout_type)
        )
        conn.commit()
        c.execute(
            'SELECT id FROM workout_sessions WHERE date=? AND workout_type=?',
            (workout_date, workout_type)
        )
        session_id = c.fetchone()['id']

        c.execute(
            '''SELECT exercise_num, set_num, weight, reps
               FROM exercise_sets WHERE session_id=?
               ORDER BY exercise_num, set_num''',
            (session_id,)
        )
        sets = [dict(row) for row in c.fetchall()]
        return jsonify({'session_id': session_id, 'sets': sets})
    finally:
        conn.close()


@app.route('/api/save_exercise', methods=['POST'])
@auth_required
def save_exercise():
    data = request.json
    session_id  = data['session_id']
    exercise_num  = data['exercise_num']
    exercise_name = data['exercise_name']
    sets = data['sets']   # [{set_num, weight, reps}]

    conn = get_db()
    try:
        c = conn.cursor()
        for s in sets:
            c.execute(
                '''INSERT OR REPLACE INTO exercise_sets
                   (session_id, exercise_num, exercise_name, set_num, weight, reps)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (session_id, exercise_num, exercise_name,
                 s['set_num'], s.get('weight'), s.get('reps'))
            )
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/history')
@auth_required
def history():
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('SELECT id, date, workout_type FROM workout_sessions ORDER BY date DESC')
        sessions = [dict(row) for row in c.fetchall()]
        for sess in sessions:
            c.execute(
                '''SELECT exercise_num, exercise_name, set_num, weight, reps
                   FROM exercise_sets WHERE session_id=?
                   ORDER BY exercise_num, set_num''',
                (sess['id'],)
            )
            sess['sets'] = [dict(row) for row in c.fetchall()]
        return jsonify(sessions)
    finally:
        conn.close()


@app.route('/api/exercises')
@auth_required
def get_exercises():
    return jsonify(EXERCISES)


@app.route('/api/session/<int:session_id>', methods=['DELETE'])
@auth_required
def delete_session(session_id):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('DELETE FROM exercise_sets WHERE session_id=?', (session_id,))
        c.execute('DELETE FROM workout_sessions WHERE id=?', (session_id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.route('/api/export')
@auth_required
def export_md():
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('SELECT id, date, workout_type FROM workout_sessions ORDER BY date ASC')
        sessions = [dict(row) for row in c.fetchall()]

        lines = ['# Дневник тренировок\n\n']

        for sess in sessions:
            lines.append(f"## {sess['date']} — Тренировка {sess['workout_type']}\n\n")
            c.execute(
                '''SELECT DISTINCT exercise_num, exercise_name
                   FROM exercise_sets WHERE session_id=?
                   ORDER BY exercise_num''',
                (sess['id'],)
            )
            exercises = c.fetchall()
            for ex in exercises:
                lines.append(f"### {ex['exercise_num']}. {ex['exercise_name']}\n\n")
                c.execute(
                    '''SELECT set_num, weight, reps FROM exercise_sets
                       WHERE session_id=? AND exercise_num=?
                       ORDER BY set_num''',
                    (sess['id'], ex['exercise_num'])
                )
                for s in c.fetchall():
                    w = f"{s['weight']} кг" if s['weight'] is not None else '—'
                    r = f"{s['reps']} повт." if s['reps'] is not None else '—'
                    lines.append(f"- Сет {s['set_num']}: {w} × {r}\n")
                lines.append('\n')
            lines.append('\n')

        content = ''.join(lines).encode('utf-8')
        buf = io.BytesIO(content)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='text/markdown; charset=utf-8',
            as_attachment=True,
            download_name='workout_history.md'
        )
    finally:
        conn.close()


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5173, debug=False)
