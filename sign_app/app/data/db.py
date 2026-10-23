"""
Database schema, migrations, and connection management.
Uses SQLite with WAL mode for better concurrency.
"""

import sqlite3
import json
import os
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Iterator
from enum import Enum
import threading


SCHEMA_VERSION = 6


class UserRole(Enum):
    LEARNER = "learner"
    INSTRUCTOR = "instructor"


class ModuleCategory(Enum):
    FINGERSPELLING = "fingerspelling"
    NUMBERS = "numbers"
    GREETINGS = "greetings"
    PHRASES = "phrases"


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AttemptResult(Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


@dataclass
class User:
    id: int
    name: str
    avatar_color: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Sign:
    id: str
    label: str
    category: ModuleCategory
    difficulty: Difficulty
    description: str
    scored: bool
    handedness: str  # "right", "left", "both"
    reference_landmarks: Optional[List[float]] = None  # Flattened 21*3 landmarks
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Module:
    id: str
    name: str
    category: ModuleCategory
    difficulty: Difficulty
    sign_ids: List[str]  # Ordered list of sign IDs
    description: str
    estimated_time_minutes: int


@dataclass
class UserProgress:
    user_id: int
    module_id: str
    completed: bool
    completed_at: Optional[datetime]
    accuracy: float
    attempts: int
    best_streak: int
    current_streak: int
    last_practiced_at: Optional[datetime]


@dataclass
class PracticeAttempt:
    id: int
    user_id: int
    sign_id: str
    module_id: Optional[str]
    result: AttemptResult
    confidence: float
    predicted_label: Optional[str]
    target_label: str
    duration_ms: int
    timestamp: datetime
    landmarks_json: Optional[str] = None


@dataclass
class QuizSession:
    id: int
    user_id: int
    module_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    score: float
    total_questions: int
    correct_count: int
    avg_time_ms: float
    weakest_signs: List[str] = field(default_factory=list)


@dataclass
class QuizQuestion:
    id: int
    session_id: int
    sign_id: str
    result: AttemptResult
    confidence: float
    predicted_label: Optional[str]
    time_ms: int
    sequence: int


@dataclass
class Badge:
    id: str
    name: str
    description: str
    icon: str
    criteria: Dict[str, Any]  # e.g., {"type": "streak", "value": 7}


@dataclass
class UserBadge:
    user_id: int
    badge_id: str
    earned_at: datetime


@dataclass
class InstructorAssignment:
    id: int
    instructor_id: int
    learner_id: int
    module_id: str
    assigned_at: datetime
    due_date: Optional[date]
    completed: bool


@dataclass
class AppSettings:
    user_id: int
    camera_device_id: str = ""
    mirror_camera: bool = True
    theme: str = "dark"
    text_size: int = 16
    dwell_duration_ms: int = 2000
    confidence_threshold: float = 0.7
    smoothing_frames: int = 5
    show_fps: bool = False
    show_perf_hud: bool = False
    hand_dwell_enabled: bool = True
    language_pack: str = "asl"
    reduced_motion: bool = False


def get_db_path() -> Path:
    """Get the database file path in the user's data directory."""
    # Honour XDG_DATA_HOME everywhere when explicitly supplied.  It is useful
    # for portable installs and tests, and prevents macOS from writing outside
    # the selected data directory.
    if os.environ.get('XDG_DATA_HOME'):
        base = Path(os.environ['XDG_DATA_HOME'])
    elif os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    elif os.name == 'posix' and 'darwin' in os.sys.platform:  # macOS
        base = Path.home() / 'Library' / 'Application Support'
    else:  # Linux
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))

    app_dir = base / 'SignLanguageApp'
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / 'app.db'


def get_connection() -> sqlite3.Connection:
    """Create a new database connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(get_db_path(), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


_thread_local = threading.local()


def get_thread_connection() -> sqlite3.Connection:
    """Get a thread-local database connection."""
    if not hasattr(_thread_local, 'conn') or _thread_local.conn is None:
        _thread_local.conn = get_connection()
    return _thread_local.conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Context manager for database transactions."""
    conn = get_thread_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Initialize the database with schema and migrations."""
    conn = get_connection()
    try:
        # Check current schema version
        cursor = conn.execute("PRAGMA user_version")
        current_version = cursor.fetchone()[0]

        if current_version == 0:
            # Check if tables already exist (database created with old version)
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            if cursor.fetchone():
                # Tables exist but no version - assume v1
                current_version = 1
            else:
                _create_schema_v1(conn)
                current_version = 1

        if current_version == 1:
            _migrate_v1_to_v2(conn)
            current_version = 2

        if current_version == 2:
            _migrate_v2_to_v3(conn)
            current_version = 3

        if current_version == 3:
            _migrate_v3_to_v4(conn)
            current_version = 4

        if current_version == 4:
            _migrate_v4_to_v5(conn)
            current_version = 5

        if current_version == 5:
            _migrate_v5_to_v6(conn)
            current_version = 6

        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.commit()
    finally:
        conn.close()


def _create_schema_v1(conn: sqlite3.Connection) -> None:
    """Create initial schema."""
    conn.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            avatar_color TEXT NOT NULL DEFAULT '#22D3EE',
            role TEXT NOT NULL DEFAULT 'learner',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            settings TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE signs (
            id TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            scored INTEGER NOT NULL DEFAULT 1,
            handedness TEXT NOT NULL DEFAULT 'both',
            reference_landmarks TEXT,
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE modules (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            sign_ids TEXT NOT NULL DEFAULT '[]',
            description TEXT NOT NULL DEFAULT '',
            estimated_time_minutes INTEGER NOT NULL DEFAULT 10
        );

        CREATE TABLE user_progress (
            user_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            completed_at TEXT,
            accuracy REAL NOT NULL DEFAULT 0.0,
            attempts INTEGER NOT NULL DEFAULT 0,
            best_streak INTEGER NOT NULL DEFAULT 0,
            current_streak INTEGER NOT NULL DEFAULT 0,
            last_practiced_at TEXT,
            PRIMARY KEY (user_id, module_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE practice_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sign_id TEXT NOT NULL,
            module_id TEXT,
            result TEXT NOT NULL,
            confidence REAL NOT NULL,
            predicted_label TEXT,
            target_label TEXT NOT NULL,
            duration_ms INTEGER NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            landmarks_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (sign_id) REFERENCES signs(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
        );

        CREATE TABLE quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT,
            score REAL NOT NULL DEFAULT 0.0,
            total_questions INTEGER NOT NULL DEFAULT 0,
            correct_count INTEGER NOT NULL DEFAULT 0,
            avg_time_ms REAL NOT NULL DEFAULT 0.0,
            weakest_signs TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            sign_id TEXT NOT NULL,
            result TEXT NOT NULL,
            confidence REAL NOT NULL,
            predicted_label TEXT,
            time_ms INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (sign_id) REFERENCES signs(id) ON DELETE CASCADE
        );

        CREATE TABLE badges (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            icon TEXT NOT NULL,
            criteria TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE user_badges (
            user_id INTEGER NOT NULL,
            badge_id TEXT NOT NULL,
            earned_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, badge_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (badge_id) REFERENCES badges(id) ON DELETE CASCADE
        );

        CREATE TABLE instructor_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            learner_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
            due_date TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (instructor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (learner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE TABLE app_settings (
            user_id INTEGER PRIMARY KEY,
            camera_device_id TEXT NOT NULL DEFAULT '',
            mirror_camera INTEGER NOT NULL DEFAULT 1,
            theme TEXT NOT NULL DEFAULT 'dark',
            text_size INTEGER NOT NULL DEFAULT 16,
            dwell_duration_ms INTEGER NOT NULL DEFAULT 2000,
            confidence_threshold REAL NOT NULL DEFAULT 0.7,
            smoothing_frames INTEGER NOT NULL DEFAULT 5,
            show_fps INTEGER NOT NULL DEFAULT 0,
            hand_dwell_enabled INTEGER NOT NULL DEFAULT 1,
            reduced_motion INTEGER NOT NULL DEFAULT 0,
            language_pack TEXT NOT NULL DEFAULT 'asl',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX idx_practice_attempts_user_sign ON practice_attempts(user_id, sign_id);
        CREATE INDEX idx_practice_attempts_timestamp ON practice_attempts(timestamp);
        CREATE INDEX idx_quiz_sessions_user ON quiz_sessions(user_id);
        CREATE INDEX idx_instructor_assignments_learner ON instructor_assignments(learner_id);
    """)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add instructor_assignments table and update settings."""
    # Check if language_pack column exists
    cursor = conn.execute("PRAGMA table_info(app_settings)")
    columns = [row[1] for row in cursor.fetchall()]
    
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS instructor_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instructor_id INTEGER NOT NULL,
            learner_id INTEGER NOT NULL,
            module_id TEXT NOT NULL,
            assigned_at TEXT NOT NULL DEFAULT (datetime('now')),
            due_date TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (instructor_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (learner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_instructor_assignments_learner ON instructor_assignments(learner_id);
    """)
    
    if "language_pack" not in columns:
        conn.execute("ALTER TABLE app_settings ADD COLUMN language_pack TEXT NOT NULL DEFAULT 'asl'")


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Schema step that required no structural change.

    init_db has always called this, but the function was never defined, so a
    database left at user_version 2 raised NameError before the app could
    start. The v1 schema already creates the columns this step would have
    added, and the later steps re-add anything missing, so an idempotent pass
    that only backfills a missing app_settings column is correct and safe.
    """
    cursor = conn.execute("PRAGMA table_info(app_settings)")
    columns = [row[1] for row in cursor.fetchall()]

    if "language_pack" not in columns:
        conn.execute("ALTER TABLE app_settings ADD COLUMN language_pack TEXT NOT NULL DEFAULT 'asl'")


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Add camera_device_id column to app_settings for stable device identification."""
    cursor = conn.execute("PRAGMA table_info(app_settings)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "camera_device_id" not in columns:
        # Add the new column
        conn.execute("ALTER TABLE app_settings ADD COLUMN camera_device_id TEXT NOT NULL DEFAULT ''")
        
        # Migrate existing camera_index to camera_device_id if possible
        # We can't do a perfect migration without the device list, but we can 
        # set a flag for the app to re-detect on first run
        conn.execute("UPDATE app_settings SET camera_device_id = '' WHERE camera_device_id = ''")
    
    if "show_perf_hud" not in columns:
        conn.execute("ALTER TABLE app_settings ADD COLUMN show_perf_hud INTEGER NOT NULL DEFAULT 0")
    
    # camera_index column is kept for backward compatibility but no longer used


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Add show_perf_hud column to app_settings."""
    cursor = conn.execute("PRAGMA table_info(app_settings)")
    columns = [row[1] for row in cursor.fetchall()]

    if "show_perf_hud" not in columns:
        conn.execute("ALTER TABLE app_settings ADD COLUMN show_perf_hud INTEGER NOT NULL DEFAULT 0")


def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Add reduced_motion column to app_settings."""
    cursor = conn.execute("PRAGMA table_info(app_settings)")
    columns = [row[1] for row in cursor.fetchall()]

    if "reduced_motion" not in columns:
        conn.execute("ALTER TABLE app_settings ADD COLUMN reduced_motion INTEGER NOT NULL DEFAULT 0")


# Repository classes for data access

class UserRepository:
    @staticmethod
    def create(name: str, avatar_color: str, role: UserRole = UserRole.LEARNER) -> User:
        with transaction() as conn:
            now = datetime.now().isoformat()
            cursor = conn.execute(
                "INSERT INTO users (name, avatar_color, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (name, avatar_color, role.value, now, now)
            )
            user_id = cursor.lastrowid
            # Create default settings
            conn.execute(
                "INSERT INTO app_settings (user_id) VALUES (?)",
                (user_id,)
            )
            return UserRepository.get_by_id(user_id)

    @staticmethod
    def get_by_id(user_id: int) -> Optional[User]:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return UserRepository._row_to_user(row)
            return None

    @staticmethod
    def get_all() -> List[User]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
            return [UserRepository._row_to_user(row) for row in rows]

    @staticmethod
    def get_learners() -> List[User]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM users WHERE role = 'learner' ORDER BY name").fetchall()
            return [UserRepository._row_to_user(row) for row in rows]

    @staticmethod
    def get_instructors() -> List[User]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM users WHERE role = 'instructor' ORDER BY name").fetchall()
            return [UserRepository._row_to_user(row) for row in rows]

    @staticmethod
    def update(user: User) -> None:
        with transaction() as conn:
            conn.execute(
                "UPDATE users SET name = ?, avatar_color = ?, role = ?, updated_at = ?, settings = ? WHERE id = ?",
                (user.name, user.avatar_color, user.role.value, datetime.now().isoformat(),
                 json.dumps(user.settings), user.id)
            )

    @staticmethod
    def delete(user_id: int) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    @staticmethod
    def _row_to_user(row: sqlite3.Row) -> User:
        return User(
            id=row['id'],
            name=row['name'],
            avatar_color=row['avatar_color'],
            role=UserRole(row['role']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            settings=json.loads(row['settings'])
        )


class SignRepository:
    @staticmethod
    def get_by_id(sign_id: str) -> Optional[Sign]:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM signs WHERE id = ?", (sign_id,)).fetchone()
            if row:
                return SignRepository._row_to_sign(row)
            return None

    @staticmethod
    def get_all() -> List[Sign]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM signs ORDER BY category, difficulty, label").fetchall()
            return [SignRepository._row_to_sign(row) for row in rows]

    @staticmethod
    def get_by_category(category: ModuleCategory) -> List[Sign]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM signs WHERE category = ? ORDER BY difficulty, label",
                (category.value,)
            ).fetchall()
            return [SignRepository._row_to_sign(row) for row in rows]

    @staticmethod
    def get_scored_signs() -> List[Sign]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM signs WHERE scored = 1 ORDER BY category, difficulty, label").fetchall()
            return [SignRepository._row_to_sign(row) for row in rows]

    @staticmethod
    def upsert(sign: Sign) -> None:
        with transaction() as conn:
            landmarks_json = json.dumps(sign.reference_landmarks) if sign.reference_landmarks else None
            conn.execute("""
                INSERT INTO signs (id, label, category, difficulty, description, scored, handedness, reference_landmarks, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    label = excluded.label,
                    category = excluded.category,
                    difficulty = excluded.difficulty,
                    description = excluded.description,
                    scored = excluded.scored,
                    handedness = excluded.handedness,
                    reference_landmarks = excluded.reference_landmarks,
                    metadata = excluded.metadata
            """, (
                sign.id, sign.label, sign.category.value, sign.difficulty.value,
                sign.description, int(sign.scored), sign.handedness,
                landmarks_json, json.dumps(sign.metadata)
            ))

    @staticmethod
    def _row_to_sign(row: sqlite3.Row) -> Sign:
        landmarks = json.loads(row['reference_landmarks']) if row['reference_landmarks'] else None
        return Sign(
            id=row['id'],
            label=row['label'],
            category=ModuleCategory(row['category']),
            difficulty=Difficulty(row['difficulty']),
            description=row['description'],
            scored=bool(row['scored']),
            handedness=row['handedness'],
            reference_landmarks=landmarks,
            metadata=json.loads(row['metadata'])
        )


class ModuleRepository:
    @staticmethod
    def get_by_id(module_id: str) -> Optional[Module]:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
            if row:
                return ModuleRepository._row_to_module(row)
            return None

    @staticmethod
    def get_all() -> List[Module]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM modules ORDER BY category, difficulty, name").fetchall()
            return [ModuleRepository._row_to_module(row) for row in rows]

    @staticmethod
    def get_by_category(category: ModuleCategory) -> List[Module]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM modules WHERE category = ? ORDER BY difficulty, name",
                (category.value,)
            ).fetchall()
            return [ModuleRepository._row_to_module(row) for row in rows]

    @staticmethod
    def upsert(module: Module) -> None:
        with transaction() as conn:
            conn.execute("""
                INSERT INTO modules (id, name, category, difficulty, sign_ids, description, estimated_time_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    difficulty = excluded.difficulty,
                    sign_ids = excluded.sign_ids,
                    description = excluded.description,
                    estimated_time_minutes = excluded.estimated_time_minutes
            """, (
                module.id, module.name, module.category.value, module.difficulty.value,
                json.dumps(module.sign_ids), module.description, module.estimated_time_minutes
            ))

    @staticmethod
    def _row_to_module(row: sqlite3.Row) -> Module:
        return Module(
            id=row['id'],
            name=row['name'],
            category=ModuleCategory(row['category']),
            difficulty=Difficulty(row['difficulty']),
            sign_ids=json.loads(row['sign_ids']),
            description=row['description'],
            estimated_time_minutes=row['estimated_time_minutes']
        )


class ProgressRepository:
    @staticmethod
    def get_progress(user_id: int, module_id: str) -> Optional[UserProgress]:
        with transaction() as conn:
            row = conn.execute(
                "SELECT * FROM user_progress WHERE user_id = ? AND module_id = ?",
                (user_id, module_id)
            ).fetchone()
            if row:
                return ProgressRepository._row_to_progress(row)
            return None

    @staticmethod
    def get_all_progress(user_id: int) -> List[UserProgress]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM user_progress WHERE user_id = ? ORDER BY module_id",
                (user_id,)
            ).fetchall()
            return [ProgressRepository._row_to_progress(row) for row in rows]

    @staticmethod
    def update_progress(progress: UserProgress) -> None:
        with transaction() as conn:
            conn.execute("""
                INSERT INTO user_progress (user_id, module_id, completed, completed_at, accuracy, attempts, best_streak, current_streak, last_practiced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, module_id) DO UPDATE SET
                    completed = excluded.completed,
                    completed_at = excluded.completed_at,
                    accuracy = excluded.accuracy,
                    attempts = excluded.attempts,
                    best_streak = excluded.best_streak,
                    current_streak = excluded.current_streak,
                    last_practiced_at = excluded.last_practiced_at
            """, (
                progress.user_id, progress.module_id, int(progress.completed),
                progress.completed_at.isoformat() if progress.completed_at else None,
                progress.accuracy, progress.attempts, progress.best_streak,
                progress.current_streak,
                progress.last_practiced_at.isoformat() if progress.last_practiced_at else None
            ))

    @staticmethod
    def _row_to_progress(row: sqlite3.Row) -> UserProgress:
        return UserProgress(
            user_id=row['user_id'],
            module_id=row['module_id'],
            completed=bool(row['completed']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            accuracy=row['accuracy'],
            attempts=row['attempts'],
            best_streak=row['best_streak'],
            current_streak=row['current_streak'],
            last_practiced_at=datetime.fromisoformat(row['last_practiced_at']) if row['last_practiced_at'] else None
        )


class AttemptRepository:
    @staticmethod
    def record(attempt: PracticeAttempt) -> int:
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO practice_attempts (user_id, sign_id, module_id, result, confidence, predicted_label, target_label, duration_ms, timestamp, landmarks_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt.user_id, attempt.sign_id, attempt.module_id,
                attempt.result.value, attempt.confidence, attempt.predicted_label,
                attempt.target_label, attempt.duration_ms, attempt.timestamp.isoformat(),
                attempt.landmarks_json
            ))
            return cursor.lastrowid

    @staticmethod
    def get_user_attempts(user_id: int, sign_id: Optional[str] = None, limit: int = 100) -> List[PracticeAttempt]:
        with transaction() as conn:
            if sign_id:
                rows = conn.execute(
                    "SELECT * FROM practice_attempts WHERE user_id = ? AND sign_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, sign_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM practice_attempts WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
                    (user_id, limit)
                ).fetchall()
            return [AttemptRepository._row_to_attempt(row) for row in rows]

    @staticmethod
    def get_accuracy_stats(user_id: int, sign_id: str) -> Dict[str, Any]:
        with transaction() as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result = 'correct' THEN 1 ELSE 0 END) as correct,
                    AVG(confidence) as avg_confidence,
                    AVG(duration_ms) as avg_duration
                FROM practice_attempts
                WHERE user_id = ? AND sign_id = ?
            """, (user_id, sign_id)).fetchone()
            return {
                'total': row['total'] or 0,
                'correct': row['correct'] or 0,
                'accuracy': (row['correct'] or 0) / (row['total'] or 1),
                'avg_confidence': row['avg_confidence'] or 0.0,
                'avg_duration_ms': row['avg_duration'] or 0
            }

    @staticmethod
    def _row_to_attempt(row: sqlite3.Row) -> PracticeAttempt:
        return PracticeAttempt(
            id=row['id'],
            user_id=row['user_id'],
            sign_id=row['sign_id'],
            module_id=row['module_id'],
            result=AttemptResult(row['result']),
            confidence=row['confidence'],
            predicted_label=row['predicted_label'],
            target_label=row['target_label'],
            duration_ms=row['duration_ms'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            landmarks_json=row['landmarks_json']
        )


class QuizRepository:
    @staticmethod
    def start_session(user_id: int, module_id: str) -> QuizSession:
        with transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO quiz_sessions (user_id, module_id, started_at) VALUES (?, ?, ?)",
                (user_id, module_id, datetime.now().isoformat())
            )
            session_id = cursor.lastrowid
            return QuizRepository.get_session(session_id)

    @staticmethod
    def get_session(session_id: int) -> Optional[QuizSession]:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)).fetchone()
            if row:
                return QuizRepository._row_to_session(row)
            return None

    @staticmethod
    def complete_session(session: QuizSession) -> None:
        with transaction() as conn:
            conn.execute("""
                UPDATE quiz_sessions
                SET completed_at = ?, score = ?, total_questions = ?, correct_count = ?, avg_time_ms = ?, weakest_signs = ?
                WHERE id = ?
            """, (
                session.completed_at.isoformat() if session.completed_at else None,
                session.score, session.total_questions, session.correct_count,
                session.avg_time_ms, json.dumps(session.weakest_signs), session.id
            ))

    @staticmethod
    def record_question(question: QuizQuestion) -> int:
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO quiz_questions (session_id, sign_id, result, confidence, predicted_label, time_ms, sequence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                question.session_id, question.sign_id, question.result.value,
                question.confidence, question.predicted_label, question.time_ms, question.sequence
            ))
            return cursor.lastrowid

    @staticmethod
    def get_user_sessions(user_id: int) -> List[QuizSession]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM quiz_sessions WHERE user_id = ? ORDER BY started_at DESC",
                (user_id,)
            ).fetchall()
            return [QuizRepository._row_to_session(row) for row in rows]

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> QuizSession:
        return QuizSession(
            id=row['id'],
            user_id=row['user_id'],
            module_id=row['module_id'],
            started_at=datetime.fromisoformat(row['started_at']),
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
            score=row['score'],
            total_questions=row['total_questions'],
            correct_count=row['correct_count'],
            avg_time_ms=row['avg_time_ms'],
            weakest_signs=json.loads(row['weakest_signs'])
        )


class BadgeRepository:
    @staticmethod
    def get_all() -> List[Badge]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM badges ORDER BY id").fetchall()
            return [BadgeRepository._row_to_badge(row) for row in rows]

    @staticmethod
    def get_user_badges(user_id: int) -> List[UserBadge]:
        with transaction() as conn:
            rows = conn.execute("SELECT * FROM user_badges WHERE user_id = ? ORDER BY earned_at DESC", (user_id,)).fetchall()
            return [BadgeRepository._row_to_user_badge(row) for row in rows]

    @staticmethod
    def award_badge(user_id: int, badge_id: str) -> bool:
        with transaction() as conn:
            try:
                conn.execute(
                    "INSERT INTO user_badges (user_id, badge_id, earned_at) VALUES (?, ?, ?)",
                    (user_id, badge_id, datetime.now().isoformat())
                )
                return True
            except sqlite3.IntegrityError:
                return False  # Already earned

    @staticmethod
    def seed_default_badges() -> None:
        """Create default badges if they don't exist."""
        badges = [
            Badge("first_letter", "First Steps", "Complete your first letter", "star", {"type": "first_completion"}),
            Badge("alphabet_master", "Alphabet Master", "Complete all fingerspelling modules", "trophy", {"type": "category_complete", "category": "fingerspelling"}),
            Badge("streak_3", "On Fire", "3-day practice streak", "flame", {"type": "streak", "value": 3}),
            Badge("streak_7", "Week Warrior", "7-day practice streak", "flame", {"type": "streak", "value": 7}),
            Badge("streak_30", "Monthly Master", "30-day practice streak", "medal", {"type": "streak", "value": 30}),
            Badge("perfect_quiz", "Perfectionist", "Score 100% on a quiz", "award", {"type": "perfect_quiz"}),
            Badge("speed_demon", "Speed Demon", "Complete a quiz under 30 seconds per question", "bolt", {"type": "fast_quiz", "avg_time_ms": 30000}),
            Badge("night_owl", "Night Owl", "Practice after 10 PM", "moon", {"type": "time_of_day", "hour": 22}),
            Badge("early_bird", "Early Bird", "Practice before 7 AM", "sun", {"type": "time_of_day", "hour": 7}),
            Badge("numbers_pro", "Numbers Pro", "Complete all number modules", "hash", {"type": "category_complete", "category": "numbers"}),
        ]
        with transaction() as conn:
            for badge in badges:
                conn.execute("""
                    INSERT OR IGNORE INTO badges (id, name, description, icon, criteria)
                    VALUES (?, ?, ?, ?, ?)
                """, (badge.id, badge.name, badge.description, badge.icon, json.dumps(badge.criteria)))

    @staticmethod
    def _row_to_badge(row: sqlite3.Row) -> Badge:
        return Badge(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            icon=row['icon'],
            criteria=json.loads(row['criteria'])
        )

    @staticmethod
    def _row_to_user_badge(row: sqlite3.Row) -> UserBadge:
        return UserBadge(
            user_id=row['user_id'],
            badge_id=row['badge_id'],
            earned_at=datetime.fromisoformat(row['earned_at'])
        )


class AssignmentRepository:
    @staticmethod
    def create(assignment: InstructorAssignment) -> int:
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO instructor_assignments (instructor_id, learner_id, module_id, assigned_at, due_date, completed)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                assignment.instructor_id, assignment.learner_id, assignment.module_id,
                assignment.assigned_at.isoformat(),
                assignment.due_date.isoformat() if assignment.due_date else None,
                int(assignment.completed)
            ))
            return cursor.lastrowid

    @staticmethod
    def get_for_learner(learner_id: int) -> List[InstructorAssignment]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM instructor_assignments WHERE learner_id = ? ORDER BY assigned_at DESC",
                (learner_id,)
            ).fetchall()
            return [AssignmentRepository._row_to_assignment(row) for row in rows]

    @staticmethod
    def get_for_instructor(instructor_id: int) -> List[InstructorAssignment]:
        with transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM instructor_assignments WHERE instructor_id = ? ORDER BY assigned_at DESC",
                (instructor_id,)
            ).fetchall()
            return [AssignmentRepository._row_to_assignment(row) for row in rows]

    @staticmethod
    def mark_completed(assignment_id: int) -> None:
        with transaction() as conn:
            conn.execute(
                "UPDATE instructor_assignments SET completed = 1 WHERE id = ?",
                (assignment_id,)
            )

    @staticmethod
    def _row_to_assignment(row: sqlite3.Row) -> InstructorAssignment:
        return InstructorAssignment(
            id=row['id'],
            instructor_id=row['instructor_id'],
            learner_id=row['learner_id'],
            module_id=row['module_id'],
            assigned_at=datetime.fromisoformat(row['assigned_at']),
            due_date=date.fromisoformat(row['due_date']) if row['due_date'] else None,
            completed=bool(row['completed'])
        )


class SettingsRepository:
    @staticmethod
    def get(user_id: int) -> AppSettings:
        with transaction() as conn:
            row = conn.execute("SELECT * FROM app_settings WHERE user_id = ?", (user_id,)).fetchone()
            if row:
                return SettingsRepository._row_to_settings(row)
            # Create default settings
            conn.execute("INSERT INTO app_settings (user_id) VALUES (?)", (user_id,))
            return AppSettings(user_id=user_id)

    @staticmethod
    def update(settings: AppSettings) -> None:
        with transaction() as conn:
            conn.execute("""
                UPDATE app_settings SET
                    camera_device_id = ?, mirror_camera = ?, theme = ?, text_size = ?,
                    dwell_duration_ms = ?, confidence_threshold = ?, smoothing_frames = ?,
                    show_fps = ?, hand_dwell_enabled = ?, language_pack = ?,
                    reduced_motion = ?
                WHERE user_id = ?
            """, (
                settings.camera_device_id, int(settings.mirror_camera), settings.theme,
                settings.text_size, settings.dwell_duration_ms, settings.confidence_threshold,
                settings.smoothing_frames, int(settings.show_fps), int(settings.hand_dwell_enabled),
                settings.language_pack, int(settings.reduced_motion), settings.user_id
            ))

    @staticmethod
    def _row_to_settings(row: sqlite3.Row) -> AppSettings:
        return AppSettings(
            user_id=row['user_id'],
            camera_device_id=row['camera_device_id'],
            mirror_camera=bool(row['mirror_camera']),
            theme=row['theme'],
            text_size=row['text_size'],
            dwell_duration_ms=row['dwell_duration_ms'],
            confidence_threshold=row['confidence_threshold'],
            smoothing_frames=row['smoothing_frames'],
            show_fps=bool(row['show_fps']),
            hand_dwell_enabled=bool(row['hand_dwell_enabled']),
            reduced_motion=bool(row['reduced_motion']) if 'reduced_motion' in row.keys() else False,
            language_pack=row['language_pack']
        )


# Export/Import utilities

def export_user_data(user_id: int) -> Dict[str, Any]:
    """Export all user data as JSON for backup/portability."""
    with transaction() as conn:
        user = UserRepository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        data = {
            'user': {
                'id': user.id,
                'name': user.name,
                'avatar_color': user.avatar_color,
                'role': user.role.value,
                'created_at': user.created_at.isoformat(),
                'settings': user.settings
            },
            'progress': [],
            'attempts': [],
            'quiz_sessions': [],
            'badges': [],
            'assignments': [],
            'app_settings': None
        }

        # Progress
        rows = conn.execute("SELECT * FROM user_progress WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            data['progress'].append(dict(row))

        # Practice attempts
        rows = conn.execute("SELECT * FROM practice_attempts WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            data['attempts'].append(dict(row))

        # Quiz sessions
        rows = conn.execute("SELECT * FROM quiz_sessions WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            session = dict(row)
            session['weakest_signs'] = json.loads(session['weakest_signs'])
            data['quiz_sessions'].append(session)

        # Quiz questions
        for session in data['quiz_sessions']:
            rows = conn.execute("SELECT * FROM quiz_questions WHERE session_id = ?", (session['id'],)).fetchall()
            session['questions'] = [dict(row) for row in rows]

        # Badges
        rows = conn.execute("SELECT * FROM user_badges WHERE user_id = ?", (user_id,)).fetchall()
        for row in rows:
            data['badges'].append(dict(row))

        # Assignments
        rows = conn.execute("SELECT * FROM instructor_assignments WHERE learner_id = ? OR instructor_id = ?", (user_id, user_id)).fetchall()
        for row in rows:
            data['assignments'].append(dict(row))

        # Settings
        row = conn.execute("SELECT * FROM app_settings WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            data['app_settings'] = dict(row)

        return data


def delete_user_data(user_id: int) -> None:
    """Delete all data for a user (GDPR/privacy compliance)."""
    with transaction() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        # CASCADE handles related tables
