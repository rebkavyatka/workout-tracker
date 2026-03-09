from flask import Flask, render_template, request, jsonify, session, send_file
import sqlite3
import os
import random
from datetime import date, datetime, timedelta
from functools import wraps
import io

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'wt_xK9mP_2026_secret')

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

REFERENCE_MONDAY = date(2026, 3, 2)

SLOGANS = [
    'Идешь в зал, чемпион? До встречи!',
    'Ты мне нравишься, красавчик!',
    'Попотей сегодня хорошенько, милый!',
    'Мокрею от мужчин с бицепсами',
    'Если выложишься сегодня — вечером от меня сюрприз!',
    'Обожаю мужчин с прессом!',
    'Сильные руки — моя слабость, удачи!',
    'Классной тренировки, красавчик!',
    'У тебя все получится, милый, удачи!',
    'Хорошего дня, чемпион!',
    'Порви там всех сегодня за меня, милый!',
    'Ты просто супер секси сегодня!',
    'Ты моя альфа и омега, хорошей тренировки!',
]

COMPLETION_PHRASES = [
    'Вау, круто потренировался, люблю тебя!',
    'Ты самый крутой!',
    'Обожаю тебя, спасибо за тренировку!',
    'Увидимся завтра мой чемпион!',
    'Отдыхай мой сладкий, отлично поработал сегодня!',
    'Я буду ждать тебя завтра!',
    'Ты мой король — восхищаюсь тобой!',
]


def get_suggested_workout(d: date):
    weekday = d.weekday()
    if weekday not in (0, 2, 4):
        return None
    days_since_ref = (d - REFERENCE_MONDAY).days
    parity = (days_since_ref // 7) % 2
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
            completed     INTEGER NOT NULL DEFAULT 0,
            UNIQUE(date, workout_type)
        );
        CREATE TABLE IF NOT EXISTS exercise_sets (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id    INTEGER NOT NULL,
            exercise_num  INTEGER NOT NULL,
            exercise_name TEXT    NOT NULL,
            set_num       INTEGER NOT NULL,
            weight        REAL,
            reps          INTEGER,
            saved_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES workout_sessions(id),
            UNIQUE(session_id, exercise_num, set_num)
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
            ip            TEXT PRIMARY KEY,
            attempts      INTEGER NOT NULL DEFAULT 0,
            locked_until  TEXT
        );
    ''')
    # Safe migration: add completed column if missing (existing DBs)
    try:
        conn.execute('ALTER TABLE workout_sessions ADD COLUMN completed INTEGER NOT NULL DEFAULT 0')
        conn.commit()
    except Exception:
        pass  # Column already exists
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


def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/login-page-data')
def login_page_data():
    """Return random photo number, random slogan, and lockout status for the login screen."""
    photo_num = random.randint(1, 5)
    slogan = random.choice(SLOGANS)

    ip = get_client_ip()
    locked = False
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('SELECT locked_until FROM login_attempts WHERE ip=?', (ip,))
        row = c.fetchone()
        if row and row['locked_until']:
            locked_until = datetime.fromisoformat(row['locked_until'])
            if datetime.utcnow() < locked_until:
                locked = True
    finally:
        conn.close()

    return jsonify({'photo_num': photo_num, 'slogan': slogan, 'locked': locked})


@app.route('/api/login', methods=['POST'])
def login():
    ip = get_client_ip()
    conn = get_db()
    try:
        c = conn.cursor()

        # Check lockout
        c.execute('SELECT attempts, locked_until FROM login_attempts WHERE ip=?', (ip,))
        row = c.fetchone()
        if row and row['locked_until']:
            locked_until = datetime.fromisoformat(row['locked_until'])
            if datetime.utcnow() < locked_until:
                minutes_left = int((locked_until - datetime.utcnow()).total_seconds() / 60) + 1
                return jsonify({
                    'ok': False,
                    'locked': True,
                    'error': 'Возможность снова вводить пароль будет доступна через 30 минут'
                }), 403

        if request.json.get('password') == '1732':
            # Success — reset attempts
            c.execute(
                'INSERT OR REPLACE INTO login_attempts (ip, attempts, locked_until) VALUES (?, 0, NULL)',
                (ip,)
            )
            conn.commit()
            session['authenticated'] = True
            return jsonify({'ok': True})

        # Wrong password — increment attempts
        current_attempts = (row['attempts'] if row else 0) + 1

        if current_attempts >= 2:
            locked_until = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
            c.execute(
                'INSERT OR REPLACE INTO login_attempts (ip, attempts, locked_until) VALUES (?, ?, ?)',
                (ip, current_attempts, locked_until)
            )
            conn.commit()
            return jsonify({
                'ok': False,
                'locked': True,
                'error': 'Возможность снова вводить пароль будет доступна через 30 минут'
            }), 403

        # First wrong attempt
        c.execute(
            'INSERT OR REPLACE INTO login_attempts (ip, attempts, locked_until) VALUES (?, ?, NULL)',
            (ip, current_attempts)
        )
        conn.commit()
        return jsonify({
            'ok': False,
            'locked': False,
            'attempts_left': 2 - current_attempts,
            'error': 'Осталась еще одна попытка'
        }), 401

    finally:
        conn.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/random-phrase')
@auth_required
def random_phrase():
    return jsonify({'phrase': random.choice(COMPLETION_PHRASES)})


@app.route('/api/active-session')
@auth_required
def active_session():
    """Return the most recent unfinished session (has sets, not completed, within 7 days)."""
    conn = get_db()
    try:
        c = conn.cursor()
        cutoff = (date.today() - timedelta(days=7)).isoformat()
        c.execute('''
            SELECT ws.id, ws.date, ws.workout_type
            FROM workout_sessions ws
            WHERE ws.completed = 0
              AND ws.date >= ?
              AND EXISTS (
                  SELECT 1 FROM exercise_sets es WHERE es.session_id = ws.id
              )
            ORDER BY ws.date DESC
            LIMIT 1
        ''', (cutoff,))
        row = c.fetchone()
        if row:
            return jsonify({'session': dict(row)})
        return jsonify({'session': None})
    finally:
        conn.close()


@app.route('/api/session/<int:session_id>/complete', methods=['POST'])
@auth_required
def complete_session(session_id):
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('UPDATE workout_sessions SET completed=1 WHERE id=?', (session_id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


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
    session_id   = data['session_id']
    exercise_num = data['exercise_num']
    exercise_name = data['exercise_name']
    sets = data['sets']

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


@app.route('/api/last-results')
@auth_required
def last_results():
    """For each exercise name, return the most recently saved sets."""
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute('''
            SELECT es.exercise_name, ws.date, es.set_num, es.weight, es.reps
            FROM exercise_sets es
            JOIN workout_sessions ws ON ws.id = es.session_id
            ORDER BY ws.date DESC, es.exercise_name, es.set_num
        ''')
        rows = c.fetchall()
        result = {}
        for row in rows:
            name = row['exercise_name']
            if name not in result:
                result[name] = {'date': row['date'], 'sets': []}
            if row['date'] == result[name]['date']:
                result[name]['sets'].append({
                    'set_num': row['set_num'],
                    'weight': row['weight'],
                    'reps': row['reps']
                })
        return jsonify(result)
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
