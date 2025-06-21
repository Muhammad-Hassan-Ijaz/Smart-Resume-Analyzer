import mysql.connector
import mysql
import os
import uuid
from datetime import datetime
import hashlib

def connect_db():
    try:
        return mysql.connector.connect(
            host="localhost",
            user="root",                 # Change to your MySQL username
            password="",                 # Change to your MySQL password
            database="signin_signup"     # Change to your DB name
        )
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def hash_password(password):
    """Hash password for secure storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed_password):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed_password

def register_user(name, email, password):
    """Register a new user with hashed password"""
    try:
        conn = connect_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            conn.close()
            return False  # Email already exists

        # Hash the password before storing
        hashed_password = hash_password(password)
        
        cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", 
                      (name, email, hashed_password))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except Exception as e:
        print("Registration error:", e)
        return False

def login_user(email, password):
    """Authenticate user login"""
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and verify_password(password, user['password']):
            # Remove password from returned user data
            del user['password']
            return user
        return None
    except Exception as e:
        print("Login error:", e)
        return None

def get_user_by_id(user_id):
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, name, email, created_at FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Exception as e:
        print("Get user error:", e)
        return None

def save_resume(user_id, filename, original_filename, file_content, file_size):
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # Generate a unique ID for the resume
        resume_id = str(uuid.uuid4())[:8]
        
        # Current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert resume metadata into database
        cursor.execute(
            "INSERT INTO resumes (id, user_id, filename, original_filename, file_size, upload_date) VALUES (%s, %s, %s, %s, %s, %s)",
            (resume_id, user_id, filename, original_filename, file_size, timestamp)
        )
        
        # Create directory for storing resume files if it doesn't exist
        upload_dir = "uploaded_resumes"
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir)
        
        # Save the file to disk
        file_path = os.path.join(upload_dir, filename)
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        conn.commit()
        conn.close()
        
        return {
            "id": resume_id,
            "user_id": user_id,
            "original_filename": original_filename,
            "filename": filename,
            "path": file_path,
            "file_size": file_size,
            "upload_date": timestamp
        }
    except Exception as e:
        print("Save resume error:", e)
        return None

def get_user_resumes(user_id):
    try:
        conn = connect_db()
        if not conn:
            return []
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM resumes WHERE user_id = %s ORDER BY upload_date DESC", 
            (user_id,)
        )
        resumes = cursor.fetchall()
        conn.close()
        
        # Add file path to each resume
        for resume in resumes:
            resume["path"] = os.path.join("uploaded_resumes", resume["filename"])
            # Ensure the file exists
            if not os.path.exists(resume["path"]):
                resume["file_missing"] = True
            else:
                resume["file_missing"] = False
        
        return resumes
    except Exception as e:
        print("Get resumes error:", e)
        return []

def get_resume_by_id(resume_id):
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM resumes WHERE id = %s", (resume_id,))
        resume = cursor.fetchone()
        conn.close()
        
        if resume:
            resume["path"] = os.path.join("uploaded_resumes", resume["filename"])
        
        return resume
    except Exception as e:
        print("Get resume error:", e)
        return None

def delete_resume(resume_id, user_id):
    try:
        conn = connect_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # First get the filename to delete the file
        cursor.execute("SELECT filename FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return False
        
        filename = result[0]
        
        # Delete from database
        cursor.execute("DELETE FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
        conn.commit()
        
        # Delete file from disk
        file_path = os.path.join("uploaded_resumes", filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        conn.close()
        return True
    except Exception as e:
        print("Delete resume error:", e)
        return False

def save_analysis_result(user_id, resume_id, job_title, job_description, match_score, analysis_text):
    try:
        conn = connect_db()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # Current timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Insert analysis result into database
        cursor.execute(
            """INSERT INTO analysis_results 
               (user_id, resume_id, job_title, job_description, match_score, analysis_text, analysis_date) 
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, resume_id, job_title, job_description, match_score, analysis_text, timestamp)
        )
        
        analysis_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        return analysis_id
    except Exception as e:
        print("Save analysis error:", e)
        return None

def get_user_analyses(user_id):
    try:
        conn = connect_db()
        if not conn:
            return []
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """SELECT a.*, r.original_filename as resume_name 
               FROM analysis_results a 
               JOIN resumes r ON a.resume_id = r.id 
               WHERE a.user_id = %s 
               ORDER BY a.analysis_date DESC""", 
            (user_id,)
        )
        analyses = cursor.fetchall()
        conn.close()
        return analyses
    except Exception as e:
        print("Get analyses error:", e)
        return []

def setup_database():
    """Create necessary tables if they don't exist"""
    try:
        conn = connect_db()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Create users table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create resumes table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumes (
            id VARCHAR(36) PRIMARY KEY,
            user_id INT NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL,
            file_size INT NOT NULL,
            upload_date DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)
        
        # Create analysis_results table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            resume_id VARCHAR(36) NOT NULL,
            job_title VARCHAR(255) NOT NULL,
            job_description TEXT NOT NULL,
            match_score VARCHAR(10) NOT NULL,
            analysis_text TEXT NOT NULL,
            analysis_date DATETIME NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE
        )
        """)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print("Database setup error:", e)
        return False

def test_database_connection():
    """Test database connection and setup"""
    try:
        conn = connect_db()
        if conn:
            print("✅ Database connection successful!")
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"📊 Total users in database: {user_count}")
            conn.close()
            return True
        else:
            print("❌ Database connection failed!")
            return False
    except Exception as e:
        print(f"❌ Database test error: {e}")
        return False
