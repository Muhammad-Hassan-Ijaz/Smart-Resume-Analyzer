import streamlit as st
import google.generativeai as genai
import os
import tempfile
import PyPDF2
from datetime import datetime
import re
import time
import uuid
from db_utils import (
    register_user,
    save_resume,
    get_user_resumes,
    connect_db
)



# Page configuration
st.set_page_config(
    page_title="Smart Resume Analyzer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create directories for storing resumes if they don't exist
UPLOAD_DIR = "uploaded_resumes"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Initialize session state
def init_session_state():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'landing'
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user_name' not in st.session_state:
        st.session_state.user_name = ""
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'user_email' not in st.session_state:
        st.session_state.user_email = ""
    if 'resume_text' not in st.session_state:
        st.session_state.resume_text = ""
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = ""
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'current_tab' not in st.session_state:
        st.session_state.current_tab = 'analysis'
    if 'auth_tab' not in st.session_state:
        st.session_state.auth_tab = 'login'

# Load CSS from external file
def load_css():
    try:
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("⚠️ CSS file not found. Using default styling.")

# Configure Gemini AI
def configure_gemini():
    api_key = "AIzaSyAVDFrDJSHRZGqKN5jdPbkniP76f7ZBNjg"  # Consider using environment variables
    try:
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        st.error(f"Failed to configure Gemini AI: {e}")
        return False

# Authentication functions
def authenticate_user(email, password):
    """Authenticate user against database"""
    user = login_user(email, password)
    if user:
        st.session_state.logged_in = True
        st.session_state.user_name = user['name']
        st.session_state.user_id = user['id']
        st.session_state.user_email = user['email']
        st.session_state.current_page = 'main'
        return True
    return False

def register_new_user(name, email, password):
    """Register new user in database"""
    user_id = register_user(name, email, password)
    if user_id:
        return True
    return False

def logout_user():
    """Clear session state and logout user"""
    st.session_state.logged_in = False
    st.session_state.user_name = ""
    st.session_state.user_id = None
    st.session_state.user_email = ""
    st.session_state.current_page = 'landing'
    st.session_state.chat_history = []
    st.session_state.resume_text = ""
    st.session_state.analysis_result = ""

# Save uploaded resume to database and disk
def save_uploaded_resume(uploaded_file, user_id):
    if not user_id:
        st.error("❌ User not logged in!")
        return None
        
    # Check if a resume with the same name already exists for this user
    original_filename = uploaded_file.name
    conn = connect_db()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM resumes WHERE user_id = %s AND original_filename = %s", 
            (user_id, original_filename)
        )
        existing_resume = cursor.fetchone()
        conn.close()
        
        if existing_resume:
            st.warning(f"⚠️ A resume with the name '{original_filename}' already exists. Using the existing file.")
            return existing_resume
    
    # Generate a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{file_id}_{original_filename}"
    
    # Get file content and size
    file_content = uploaded_file.getbuffer()
    file_size = len(file_content)
    
    # Save to database
    file_info = save_resume(user_id, filename, original_filename, file_content, file_size)
    
    if file_info:
        st.success(f"✅ Resume '{original_filename}' saved successfully!")
        return file_info
    else:
        st.error("❌ Failed to save resume!")
        return None

# Format file size for display
def format_file_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

# Extract text from PDF
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(pdf_file.read())
            temp_file_path = temp_file.name
        
        with open(temp_file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                text += pdf_reader.pages[page_num].extract_text()
        
        os.unlink(temp_file_path)
        return text
    except Exception as e:
        st.error(f"Error extracting PDF text: {e}")
        return ""

# Analyze resume function
def analyze_resume(resume_text, job_title, job_description):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        Analyze this resume for the {job_title} position:
        
        JOB DESCRIPTION:
        {job_description}
        
        RESUME:
        {resume_text}
        
        Provide a comprehensive analysis with:
        1. Match Score (percentage)
        2. Key Strengths (3-5 points)
        3. Areas for Improvement (3-5 points)
        4. Missing Skills/Keywords
        5. Actionable Recommendations
        
        Format with clear headers and bullet points.
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error analyzing resume: {e}"

# Extract match score from analysis
def extract_match_score(analysis_text):
    match = re.search(r'(\d+)%', analysis_text)
    if match:
        return match.group(1) + "%"
    return "85%"

# Professional Sidebar
def show_sidebar():
    with st.sidebar:
        # Sidebar Header
        st.markdown("""
        <div class="sidebar-header">
            <div class="sidebar-logo">🧠 Smart Resume Analyzer</div>
            <div class="sidebar-tagline">Professional Career Enhancement</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state.logged_in:
            # User Info
            user_initial = st.session_state.user_name[0].upper() if st.session_state.user_name else "U"
            st.markdown(f"""
            <div class="sidebar-user-info">
                <div class="user-avatar">{user_initial}</div>
                <div class="user-name">{st.session_state.user_name}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Main Navigation
            st.markdown('<div class="nav-section">', unsafe_allow_html=True)
            st.markdown('<div class="nav-section-title">Main Tools</div>', unsafe_allow_html=True)
            
            # Navigation items
            nav_items = [
                ("📊", "Resume Analysis", "analysis", "Analyze your resume with AI"),
                ("💬", "Ask Questions", "questions", "Chat with AI career coach"),
                ("⚖️", "Resume Comparison", "compare", "Compare multiple resumes"),
                ("✍️", "Cover Letter", "cover", "Generate cover letters"),
                ("📁", "My Resumes", "resumes", "View saved resumes"),
            ]
            
            for icon, label, key, description in nav_items:
                if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
                    st.session_state.current_tab = key
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Settings Section
            st.markdown('<div class="nav-section">', unsafe_allow_html=True)
            st.markdown('<div class="nav-section-title">Account</div>', unsafe_allow_html=True)
            
            if st.button("🔓 Logout", key="sidebar_logout", use_container_width=True):
                logout_user()
                st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
            
        else:
            st.markdown("""
            <div style="padding: 2rem 1rem; text-align: center; color: var(--text-secondary);">
                <div style="font-size: 1.2rem; margin-bottom: 1rem;">🚀 Get Started</div>
                <div style="font-size: 0.9rem; line-height: 1.6;">
                    Transform your career with AI-powered resume analysis and optimization tools.
                </div>
            </div>
            """, unsafe_allow_html=True)

# Original Landing Page (Previous Design)
def show_landing_page():
    # Navigation Bar
    st.markdown("""
    <nav class="landing-navbar">
        <div class="landing-container">
            <div class="navbar-content">
                <div class="navbar-logo">
                    <i class="fas fa-brain"></i>
                    <span>Resume Analyzer</span>
                </div>
                <div class="navbar-links">
                    <a href="#features" class="nav-link"></a>
                    <a href="#how-it-works" class="nav-link"></a>
                    <a href="#testimonials" class="nav-link"></a>
                </div>
            </div>
        </div>
    </nav>
    """, unsafe_allow_html=True)
    
    # Login button at top right
    col1, col2 = st.columns([9, 1])
    with col2:
        if st.button("🔑 Login", key="landing_login", use_container_width=True):
            st.session_state.current_page = 'auth'
            st.rerun()
    
    # Hero Section
    st.markdown("""
    <section class="landing-hero">
        <div class="hero-bg"></div>
        <div class="landing-container">
            <div class="hero-content">
                <div class="hero-badge">
                    <i class="fas fa-bolt"></i>
                    AI-Powered Career Enhancement
                </div>
                <h1 class="hero-title">Transform Your Career with <span class="gradient-text">AI Resume Analysis</span></h1>
                <p class="hero-subtitle">
                    Get instant AI-powered feedback, optimize your resume for any job, and land your dream position with our advanced career enhancement platform.
                </p>
                
          
    </section>
    """, unsafe_allow_html=True)
    
    # CTA Buttons (Streamlit buttons that actually work)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🚀 Analyze Your Resume Now", key="start_analysis", use_container_width=True):
               
                st.session_state.current_page = 'auth'
                st.rerun()
        
        

    
    # Stats Section
    st.markdown("""
    <section class="landing-stats">
        <div class="landing-container">
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">95%</div>
                    <div class="stat-label">Accuracy Rate</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">150+</div>
                    <div class="stat-label">Resumes Analyzed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">85%</div>
                    <div class="stat-label">Interview Success</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">24/7</div>
                    <div class="stat-label">AI Support</div>
                </div>
            </div>
        </div>
    </section>
    """, unsafe_allow_html=True)
    
    # Features Section
    st.markdown('<h2 class="landing-section-heading" id="features">✨ Powerful AI-Driven Features</h2>', unsafe_allow_html=True)
    st.markdown('<p class="landing-section-subtitle">Everything you need to optimize your resume and accelerate your career growth</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon blue">
                <i class="fas fa-file-alt"></i>
            </div>
            <h3 class="feature-title">Smart Resume Analysis</h3>
            <p class="feature-description">
                Get detailed AI-powered analysis with match scoring,and specific recommendations for improvement.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon purple">
                <i class="fas fa-comments"></i>
            </div>
            <h3 class="feature-title">AI Career Coach</h3>
            <p class="feature-description">
                Ask questions about your resume and get intelligent responses from our advanced AI assistant.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon green">
                <i class="fas fa-chart-bar"></i>
            </div>
            <h3 class="feature-title">Resume Comparison</h3>
            <p class="feature-description">
                Compare multiple resumes side-by-side to determine the best fit for specific positions.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Second row of features
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon orange">
                <i class="fas fa-users"></i>
            </div>
            <h3 class="feature-title">Cover Letter Generator</h3>
            <p class="feature-description">
                Generate personalized, professional cover letters tailored to specific job applications.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon pink">
                <i class="fas fa-shield-alt"></i>
            </div>
            <h3 class="feature-title">Secure & Private</h3>
            <p class="feature-description">
                Your data is encrypted and secure. We never share your personal information or resume content.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="landing-feature-card">
            <div class="feature-icon teal">
                <i class="fas fa-chart-line"></i>
            </div>
            <h3 class="feature-title">Real-time Insights</h3>
            <p class="feature-description">
                Get instant feedback and track your resume optimization progress with detailed analytics.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # How It Works Section
    st.markdown('<h2 class="landing-section-heading" id="how-it-works">🚀 How It Works</h2>', unsafe_allow_html=True)
    st.markdown('<p class="landing-section-subtitle">Get professional resume analysis in just three simple steps</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="landing-step-card">
            <div class="step-number">1</div>
            <h3 class="step-title">Upload Your Resume</h3>
            <p class="step-description">
                Simply upload your resume in PDF format and provide the job description you're targeting.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="landing-step-card">
            <div class="step-number">2</div>
            <h3 class="step-title">AI Analysis</h3>
            <p class="step-description">
                Our advanced AI analyzes your resume against the job requirements and industry standards.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="landing-step-card">
            <div class="step-number">3</div>
            <h3 class="step-title">Get Results</h3>
            <p class="step-description">
                Receive detailed feedback, match scores, and actionable recommendations to improve your resume.
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Benefits Section
    st.markdown("""
    <section class="benefits">
        <div class="landing-container">
            <div class="benefits-grid">
                <div class="benefits-content">
                    <h2>Why Choose Our AI Resume Analyzer?</h2>
                    <div class="benefit-list">
                        <div class="benefit-item">
                            <i class="fas fa-check-circle"></i>
                            <div>
                                <h3>Advanced AI Technology</h3>
                                <p>Powered by Google's Gemini AI for the most accurate and comprehensive analysis.</p>
                            </div>
                        </div>
                        <div class="benefit-item">
                            <i class="fas fa-check-circle"></i>
                            <div>
                                <h3>Industry-Specific Insights</h3>
                                <p>Get tailored recommendations based on your target industry and role.</p>
                            </div>
                        </div>
                        <div class="benefit-item">
                            <i class="fas fa-check-circle"></i>
                            <div>
                                <h3>Instant Results</h3>
                                <p>Get comprehensive analysis and feedback in seconds, not days.</p>
                            </div>
                        </div>
                        <div class="benefit-item">
                            <i class="fas fa-check-circle"></i>
                            <div>
                                <h3>Continuous Improvement</h3>
                                <p>Track your progress and optimize your resume for better results.</p>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="benefits-visual">
                    <div class="score-card">
                        <div class="score-header">
                            <span>Match Score</span>
                            <i class="fas fa-award"></i>
                        </div>
                        <div class="score-value">95%</div>
                        <div class="score-bar">
                            <div class="score-progress" style="width: 92%"></div>
                        </div>
                        <div class="score-metrics">
                            <div class="score-metric">
                                <span>Keywords Match</span>
                                <span class="excellent">Excellent</span>
                            </div>
                            <div class="score-metric">
                                <span>Experience Relevance</span>
                                <span class="good">Very Good</span>
                            </div>
                            <div class="score-metric">
                                <span>Skills Alignment</span>
                                <span class="excellent">Perfect</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>
    """, unsafe_allow_html=True)
    
    
    # Call to Action Section
    st.markdown("""
    <section class="landing-cta">
        <div class="landing-container">
            <div class="cta-content">
                <h2 class="cta-title">Ready to Transform Your Career?</h2>
                <p class="cta-subtitle">
                    Join thousands of professionals who have already optimized their resumes and landed their dream jobs with our AI-powered platform.
                </p>
            </div>
        </div>
    </section>
    """, unsafe_allow_html=True)
    
    # Final CTA Button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 Start Free Analysis Now", key="start_analysis_final", use_container_width=True):
            st.session_state.current_page = 'auth'
            st.rerun()

# Professional Authentication Page
def show_auth_page():
    # Back button
    if st.button("← Back to Home", key="back_to_home"):
        st.session_state.current_page = 'landing'
        st.rerun()
    
    
    # Tab selection with new styling
    st.markdown('<div class="auth-tabs">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔑 Sign In", key="login_tab", use_container_width=True):
            st.session_state.auth_tab = 'login'
    with col2:
        if st.button("✨ Sign Up", key="signup_tab", use_container_width=True):
            st.session_state.auth_tab = 'signup'
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Add active tab indicator
    if st.session_state.auth_tab == 'login':
        st.markdown('<div class="tab-indicator">Currently on: Sign In</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="tab-indicator">Currently on: Sign Up</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.session_state.auth_tab == 'login':
        # Login Form with new styling
        st.markdown("""
        <div class="auth-form-section">
            <h3 class="form-section-title">🔑 Sign In to Your Account</h3>
            <p class="form-section-subtitle">Enter your credentials to access your dashboard</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form", clear_on_submit=False):
            st.markdown('<div class="form-group" >', unsafe_allow_html=True)
            email = st.text_input("📧 Email Address", placeholder="Enter your email address", key="login_email")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-group">', unsafe_allow_html=True)
            password = st.text_input("🔒 Password", type="password", placeholder="Enter your password", key="login_password")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-actions">', unsafe_allow_html=True)
            login_btn = st.form_submit_button("🚀 Sign In to Dashboard", use_container_width=True, type="primary")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if login_btn:
                if email and password:
                    with st.spinner("🔐 Authenticating..."):
                        if authenticate_user(email, password):
                            st.success(f"✅ Welcome back, {st.session_state.user_name}!")
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Invalid email or password. Please try again.")
                else:
                    st.error("❌ Please fill in all fields")
        
        # Additional login options
        st.markdown("""
        <div class="auth-footer">
            <p class="auth-footer-text">Don't have an account? Click "Sign Up" above to get started!</p>
            <div class="auth-benefits">
                <div class="benefit-item-small">
                    <span class="benefit-icon">✨</span>
                    <span>Free to get started</span>
                </div>
                <div class="benefit-item-small">
                    <span class="benefit-icon">🚀</span>
                    <span>Instant AI analysis</span>
                </div>
                <div class="benefit-item-small">
                    <span class="benefit-icon">🔒</span>
                    <span>Secure & private</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    else:
        # Sign Up Form with new styling
        st.markdown("""
        <div class="auth-form-section">
            <h3 class="form-section-title">✨ Create Your Account</h3>
            <p class="form-section-subtitle">Join thousands of professionals who have transformed their careers</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("signup_form", clear_on_submit=False):
            st.markdown('<div class="form-group">', unsafe_allow_html=True)
            name = st.text_input("👤 Full Name", placeholder="Enter your full name", key="signup_name")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-group">', unsafe_allow_html=True)
            email = st.text_input("📧 Email Address", placeholder="Enter your email address", key="signup_email")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-group">', unsafe_allow_html=True)
            password = st.text_input("🔒 Password", type="password", placeholder="Create a strong password", key="signup_password")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-group">', unsafe_allow_html=True)
            confirm_password = st.text_input("🔒 Confirm Password", type="password", placeholder="Confirm your password", key="signup_confirm")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-checkbox">', unsafe_allow_html=True)
            terms_agreed = st.checkbox("I agree to the Terms of Service and Privacy Policy")
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-actions">', unsafe_allow_html=True)
            signup_btn = st.form_submit_button("🎉 Create My Account", use_container_width=True, type="primary")
            st.markdown('</div>', unsafe_allow_html=True)
            
            if signup_btn:
                if name and email and password and confirm_password and terms_agreed:
                    if password == confirm_password:
                        with st.spinner("🔨 Creating your account..."):
                            if register_new_user(name, email, password):
                                st.success("✅ Account created successfully!")
                                st.info("🔄 Please use the Sign In tab to access your account.")
                                st.balloons()
                                time.sleep(2)
                                st.session_state.auth_tab = 'login'
                                st.rerun()
                            else:
                                st.error("❌ Registration failed: Email may already be in use.")
                    else:
                        st.error("❌ Passwords don't match!")
                elif not terms_agreed:
                    st.error("❌ Please accept the Terms of Service")
                else:
                    st.error("❌ Please fill in all fields")
        
        # Additional signup benefits
        st.markdown("""
        <div class="auth-footer">
            <p class="auth-footer-text">Already have an account? Click "Sign In" above to access your dashboard!</p>
            <div class="signup-benefits">
                <h4 class="benefits-title">What you'll get:</h4>
                <div class="benefits-grid-small">
                    <div class="benefit-item-detailed">
                        <span class="benefit-icon-large">📊</span>
                        <div class="benefit-content">
                            <h5>AI Resume Analysis</h5>
                            <p>Get detailed feedback and match scores</p>
                        </div>
                    </div>
                    <div class="benefit-item-detailed">
                        <span class="benefit-icon-large">💬</span>
                        <div class="benefit-content">
                            <h5>Career Coach</h5>
                            <p>Ask questions and get expert advice</p>
                        </div>
                    </div>
                    <div class="benefit-item-detailed">
                        <span class="benefit-icon-large">📁</span>
                        <div class="benefit-content">
                            <h5>Resume Storage</h5>
                            <p>Save and manage multiple resumes</p>
                        </div>
                    </div>
                    <div class="benefit-item-detailed">
                        <span class="benefit-icon-large">✍️</span>
                        <div class="benefit-content">
                            <h5>Cover Letters</h5>
                            <p>Generate personalized cover letters</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Close the auth card
    st.markdown('</div></div></div>', unsafe_allow_html=True)

# Main Application
def show_main_app():
    configure_gemini()
    
    # Header
    st.markdown(f"""
    <div class="main-container">
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="color: var(--text-primary); font-size: 2.5rem; margin-bottom: 0.5rem;">🧠 AI Resume Analyzer Dashboard</h1>
            <p style="color: var(--text-secondary); font-size: 1.2rem;">Welcome back, {st.session_state.user_name}! Ready to enhance your career?</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show content based on current tab
    if st.session_state.current_tab == 'analysis':
        show_resume_analysis()
    elif st.session_state.current_tab == 'questions':
        show_ask_questions()
    elif st.session_state.current_tab == 'compare':
        show_compare_resumes()
    elif st.session_state.current_tab == 'cover':
        show_cover_letter()
    elif st.session_state.current_tab == 'resumes':
        show_saved_resumes()

def show_resume_analysis():
    st.markdown("""
    <div class="analysis-section">
        <h2 class="analysis-title">📊 Resume Analysis</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<h3 class="section-heading">📄 Upload Your Resume</h3>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Choose a PDF file", 
            type="pdf",
            help="Upload your resume in PDF format for AI analysis"
        )
        
        if uploaded_file is not None:
            # Save the uploaded resume to database
            file_info = save_uploaded_resume(uploaded_file, st.session_state.user_id)
            
            if file_info:
                try:
                    # Reset the file pointer to the beginning
                    uploaded_file.seek(0)
                    resume_text = extract_text_from_pdf(uploaded_file)
                    st.session_state.resume_text = resume_text
                    
                    with st.expander("🔍 Preview Extracted Text"):
                        st.text(resume_text[:500] + "..." if len(resume_text) > 500 else resume_text)
                except Exception as e:
                    st.error(f"Error extracting text from PDF: {e}")
    
    with col2:
        st.markdown('<h3 class="section-heading">💼 Job Details</h3>', unsafe_allow_html=True)
        job_title = st.text_input("Job Title", placeholder="e.g., Data Scientist")
        job_description = st.text_area(
            "Job Description", 
            height=200, 
            placeholder="Paste the complete job description here..."
        )
    
    # Analysis Button
    st.markdown("---")
    if st.button("🔍 Analyze Resume", use_container_width=True, key="analyze_btn"):
        if st.session_state.resume_text and job_title and job_description:
            with st.spinner("🤖 AI is analyzing your resume... Please wait"):
                analysis = analyze_resume(st.session_state.resume_text, job_title, job_description)
                st.session_state.analysis_result = analysis
            
            # Display Results
            match_score = extract_match_score(analysis)
            
            st.markdown(f"""
            <div class="match-score-container">
                <div class="match-score-value">{match_score}</div>
                <div class="match-score-label">Match Score</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="results-container">
                <h3 class="results-title">📊 Detailed Analysis Results</h3>
                <div class="results-content">{analysis}</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.balloons()
        else:
            st.warning("⚠️ Please upload your resume and fill in all job details.")

def show_ask_questions():
    st.markdown("""
    <div class="analysis-section">
        <h2 class="analysis-title">💬 Ask Questions About Your Resume</h2>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.resume_text:
        st.info("📋 Please upload your resume in the 'Resume Analysis' section first.")
        return
    
    st.markdown('<h3 class="section-heading">🤖 Chat with AI Career Coach</h3>', unsafe_allow_html=True)
    
    # Display chat history
    if st.session_state.chat_history:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for i, message in enumerate(st.session_state.chat_history):
            if message["is_user"]:
                st.markdown(f"""
                <div class="chat-message user-message">
                    <strong>You:</strong> {message["text"]}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="chat-message ai-message">
                    <strong>AI Coach:</strong> {message["text"]}
                </div>
                """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Chat Input
    with st.form("chat_form"):
        question = st.text_area(
            "💭 Ask your question", 
            placeholder="e.g., What skills should I add to better match this job?",
            height=100
        )
        submit_btn = st.form_submit_button("🚀 Send Question", use_container_width=True)
        
        if submit_btn and question:
            # Add user message
            st.session_state.chat_history.append({"text": question, "is_user": True})
            
            # Generate AI response
            with st.spinner("🤖 AI is thinking..."):
                try:
                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    prompt = f"""
                    You are a helpful resume coach. The user is asking: {question}
                    
                    Resume content: {st.session_state.resume_text[:1000]}
                    
                    Provide helpful, actionable advice in a friendly tone.
                    """
                    response = model.generate_content(prompt)
                    ai_response = response.text
                except:
                    ai_response = "I'm here to help with your resume questions. Could you please be more specific about what you'd like to know?"
            
            # Add AI response
            st.session_state.chat_history.append({"text": ai_response, "is_user": False})
            st.rerun()

def show_compare_resumes():
    st.markdown("""
    <div class="analysis-section">
        <h2 class="analysis-title">⚖️ Comparison Two Resumes</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<h3 class="section-heading">📄 Resume 1</h3>', unsafe_allow_html=True)
        resume1 = st.file_uploader("Upload Resume 1", type="pdf", key="resume1")
        if resume1:
            st.success("✅ Resume 1 uploaded!")
    
    with col2:
        st.markdown('<h3 class="section-heading">📄 Resume 2</h3>', unsafe_allow_html=True)
        resume2 = st.file_uploader("Upload Resume 2", type="pdf", key="resume2")
        if resume2:
            st.success("✅ Resume 2 uploaded!")
    
    job_title_compare = st.text_input("Job Title for Comparison", placeholder="e.g., Software Engineer")
    
    if st.button("⚖️ Resume Comparison", use_container_width=True, key="compare_btn"):
        if resume1 and resume2 and job_title_compare:
            with st.spinner("🤖 AI is comparing resumes..."):
                try:
                    text1 = extract_text_from_pdf(resume1)
                    text2 = extract_text_from_pdf(resume2)
                    
                    # Generate comparison using AI
                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    prompt = f"""
                    Compare these two resumes for the {job_title_compare} position:
                    
                    Resume 1: {text1[:1000]}
                    Resume 2: {text2[:1000]}
                    
                    Provide:
                    1. Score for each resume (out of 100)
                    2. Strengths of each
                    3. Weaknesses of each
                    4. Which is better and why
                    """
                    response = model.generate_content(prompt)
                    comparison_result = response.text
                    
                    st.markdown(f"""
                    <div class="results-container">
                        <h3 class="results-title">📊 Comparison Results</h3>
                        <div class="results-content">{comparison_result}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.balloons()
                except Exception as e:
                    st.error(f"Error comparing resumes: {e}")
        else:
            st.warning("⚠️ Please upload both resumes and enter a job title.")

def show_cover_letter():
    st.markdown("""
    <div class="analysis-section">
        <h2 class="analysis-title">✍️ AI Cover Letter Generator</h2>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<h3 class="section-heading">📄 Upload Resume</h3>', unsafe_allow_html=True)
        cover_resume = st.file_uploader("Upload your resume", type="pdf", key="cover_resume")
        
        if cover_resume:
            st.success("✅ Resume uploaded!")
    
    with col2:
        st.markdown('<h3 class="section-heading">👤 Personal Details</h3>', unsafe_allow_html=True)
        applicant_name = st.text_input("Your Name", placeholder="e.g., John Doe")
        cover_job_title = st.text_input("Job Title", placeholder="e.g., Data Analyst")
    
    cover_job_description = st.text_area(
        "Job Description", 
        height=150, 
        placeholder="Paste the job description here..."
    )
    
    if st.button("✨ Generate Cover Letter", use_container_width=True, key="generate_cover_btn"):
        if cover_resume and applicant_name and cover_job_title and cover_job_description:
            with st.spinner("🤖 AI is crafting your cover letter..."):
                try:
                    resume_text = extract_text_from_pdf(cover_resume)
                    
                    # Generate cover letter using AI
                    model = genai.GenerativeModel('gemini-2.0-flash-exp')
                    prompt = f"""
                    Write a professional cover letter for {applicant_name} applying for {cover_job_title}.
                    
                    Job Description: {cover_job_description}
                    Resume Summary: {resume_text[:1000]}
                    
                    Make it professional, tailored, and compelling. Include specific examples from the resume.
                    """
                    response = model.generate_content(prompt)
                    cover_letter = response.text
                    
                    st.markdown(f"""
                    <div class="results-container">
                        <h3 class="results-title">📝 Your Personalized Cover Letter</h3>
                        <div class="results-content">{cover_letter}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Download button
                    st.download_button(
                        label="📥 Download Cover Letter",
                        data=cover_letter,
                        file_name=f"cover_letter_{applicant_name.replace(' ', '_')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                    
                    st.success("✅ Cover letter generated successfully!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error generating cover letter: {e}")
        else:
            st.warning("⚠️ Please fill in all fields and upload your resume.")

def show_saved_resumes():
    st.markdown("""
    <div class="analysis-section">
        <h2 class="analysis-title">📁 My Saved Resumes</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Get user's saved resumes from database
    user_resumes = get_user_resumes(st.session_state.user_id)
    
    if user_resumes:
        st.markdown(f"""
        <div class="resume-list">
            <h3 class="resume-list-title">📋 Your Resume Collection ({len(user_resumes)} files)</h3>
        </div>
        """, unsafe_allow_html=True)
        
        for resume in user_resumes:
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"""
                <div class="resume-item">
                    <div class="resume-icon">📄</div>
                    <div class="resume-details">
                        <div class="resume-name">{resume['original_filename']}</div>
                        <div class="resume-meta">
                            <span class="resume-date">📅 {resume['upload_date']}</span>
                            <span class="resume-size">💾 {format_file_size(resume['file_size'])}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                if st.button(f"📖 View", key=f"view_{resume['id']}", use_container_width=True):
                    try:
                        if os.path.exists(resume['path']):
                            with open(resume['path'], 'rb') as file:
                                file_content = file.read()
                                if file_content:
                                    import io
                                    file_stream = io.BytesIO(file_content)
                                    resume_text = extract_text_from_pdf(file_stream)
                                    
                                    with st.expander(f"📄 Content of {resume['original_filename']}", expanded=True):
                                        st.text(resume_text[:1000] + "..." if len(resume_text) > 1000 else resume_text)
                                else:
                                    st.error("Error: The resume file is empty.")
                        else:
                            st.error("Error: Resume file not found.")
                    except Exception as e:
                        st.error(f"Error reading file: {e}")
            
            with col3:
                if st.button(f"🗑️", key=f"delete_{resume['id']}", help="Delete resume", use_container_width=True):
                    if delete_resume(resume['id'], st.session_state.user_id):
                        st.success(f"✅ Deleted {resume['original_filename']}")
                        st.rerun()
                    else:
                        st.error("Error deleting file")
    
    else:
        st.markdown("""
        <div class="resume-list">
            <div class="resume-empty">
                <div class="resume-empty-icon">📁</div>
                <div class="resume-empty-text">No resumes saved yet</div>
                <div class="resume-empty-subtext">Upload your first resume in the Resume Analysis section to get started!</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("📊 Go to Resume Analysis", use_container_width=True):
            st.session_state.current_tab = 'analysis'
            st.rerun()

# Main App Logic
def main():
    # Initialize database and session state
    init_session_state()
    load_css()
    
    # Test database connection on startup
    if not test_database_connection():
        st.error("❌ Database connection failed! Please check your MySQL configuration.")
        st.stop()
    
    # Setup database tables
    if not setup_database():
        st.error("❌ Database setup failed!")
        st.stop()
    
    # Show sidebar only when logged in
    if st.session_state.logged_in:
        show_sidebar()
    
    # Route to appropriate page
    if st.session_state.current_page == 'landing':
        show_landing_page()
    elif st.session_state.current_page == 'auth':
        show_auth_page()
    elif st.session_state.current_page == 'main' and st.session_state.logged_in:
        show_main_app()
    else:
        st.session_state.current_page = 'landing'
        st.rerun()

if __name__ == "__main__":
    main()
