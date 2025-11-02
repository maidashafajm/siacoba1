import streamlit as st
import requests
import sqlite3
import hashlib
import re
from datetime import datetime
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import plotly.express as px
import plotly.graph_objects as go


# Konfigurasi halaman
st.set_page_config(
    page_title="Tilapia Suite",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== KONFIGURASI SUPABASE =====
SUPABASE_URL = "https://paoneuhqmmtbdnsduiwv.supabase.co"  # ← GANTI INI
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBhb25ldWhxbW10YmRuc2R1aXd2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjIwNTE5MTEsImV4cCI6MjA3NzYyNzkxMX0.uEiuiYfGDxuuObMve_yWIPvlf3wq0ZwiOs1pdv6XhWg"  # ← GANTI INI (anon public key)

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def supabase_select(table):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select=*"
    r = requests.get(url, headers=headers)
    return r.json()

def supabase_insert(table, data: dict):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = requests.post(url, json=data, headers=headers)
    return r.json()

AUTH_URL = f"{SUPABASE_URL}/auth/v1"
# fungsi supabase signup
def supabase_signup(email, password, username, role):
    data = {
        "email": email,
        "password": password,
        "options": {
            "email_redirect_to": "https://siacoba1-4aazpzevgfmcxpegbymy24.streamlit.app/?page=verify",  # ← URL app kamu
            "data": {
                "username": username,
                "role": role
            }
        }
    }
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    res = requests.post(f"{AUTH_URL}/signup", json=data, headers=headers)
    return res.json()
# fungsi supabase login
def supabase_login(email, password):
    data = {"email": email, "password": password}
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    res = requests.post(f"{AUTH_URL}/token?grant_type=password", json=data, headers=headers)
    data = res.json()

    # ✅ Cek error dulu
    if "error" in data or res.status_code != 200:
        return {"success": False, "error": data.get("error_description", "Login gagal")}

    # ✅ Ambil user & token aman
    user_info = data.get("user")
    access_token = data.get("access_token")

    if not user_info or not access_token:
        return {"success": False, "error": "Login gagal, data tidak lengkap"}

    return {
        "success": True,
        "user_id": user_info.get("id"),
        "email": user_info.get("email"),
        "access_token": access_token
    }
# fungsi supabase forgot password
def supabase_forgot_password(email):
    data = {
        "email": email,
        "options": {
            "redirect_to": "https://siacoba1-4aazpzevgfmcxpegbymy24.streamlit.app/?page=reset_password"  # ← URL app kamu
        }
    }
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    res = requests.post(f"{AUTH_URL}/recover", json=data, headers=headers)
    return res.json()

# Inisialisasi database
def init_db():
    conn = sqlite3.connect('tilapia_suite.db', check_same_thread=False)
    c = conn.cursor()
    
    # Tabel users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        verified INTEGER DEFAULT 0,
        verification_token TEXT,
        reset_token TEXT,
        nama_lengkap TEXT,
        no_telepon TEXT,
        alamat TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Tabel transaksi penjualan (dari kasir)
    c.execute('''CREATE TABLE IF NOT EXISTS transaksi_penjualan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        no_struk TEXT UNIQUE NOT NULL,
        tanggal DATE NOT NULL,
        waktu TIME NOT NULL,
        jumlah_kg REAL NOT NULL,
        harga_per_kg REAL NOT NULL,
        total REAL NOT NULL,
        metode_bayar TEXT NOT NULL,
        kasir_id INTEGER,
        status TEXT DEFAULT 'selesai',
        FOREIGN KEY (kasir_id) REFERENCES users(id)
    )''')
    
    # Tabel chart of accounts (daftar akun)
    c.execute('''CREATE TABLE IF NOT EXISTS chart_of_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kode_akun TEXT UNIQUE NOT NULL,
        nama_akun TEXT NOT NULL,
        kategori TEXT NOT NULL,
        saldo_normal TEXT NOT NULL
    )''')
    
    # Tabel neraca saldo awal
    c.execute('''CREATE TABLE IF NOT EXISTS neraca_saldo_awal (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periode TEXT NOT NULL,
        kode_akun TEXT NOT NULL,
        debit REAL DEFAULT 0,
        kredit REAL DEFAULT 0,
        FOREIGN KEY (kode_akun) REFERENCES chart_of_accounts(kode_akun)
    )''')
    
    # Tabel jurnal umum
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_umum (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        kode_akun TEXT NOT NULL,
        keterangan TEXT,
        debit REAL DEFAULT 0,
        kredit REAL DEFAULT 0,
        ref TEXT,
        FOREIGN KEY (kode_akun) REFERENCES chart_of_accounts(kode_akun)
    )''')
    
    # Tabel jurnal khusus penjualan
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_penjualan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        no_faktur TEXT,
        keterangan TEXT,
        debit_kas REAL DEFAULT 0,
        kredit_penjualan REAL DEFAULT 0,
        debit_hpp REAL DEFAULT 0,
        kredit_persediaan REAL DEFAULT 0
    )''')
    
    # Tabel jurnal khusus pembelian
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_pembelian (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        no_faktur TEXT,
        keterangan TEXT,
        debit_pembelian REAL DEFAULT 0,
        kredit_kas REAL DEFAULT 0,
        debit_persediaan REAL DEFAULT 0
    )''')
    
    # Tabel jurnal penerimaan kas
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_penerimaan_kas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        no_bukti TEXT,
        keterangan TEXT,
        debit_kas REAL DEFAULT 0,
        kredit_akun TEXT,
        kredit_nominal REAL DEFAULT 0
    )''')
    
    # Tabel jurnal pengeluaran kas
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_pengeluaran_kas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        no_bukti TEXT,
        keterangan TEXT,
        debit_akun TEXT,
        debit_nominal REAL DEFAULT 0,
        kredit_kas REAL DEFAULT 0
    )''')
    
    # Tabel aset
    c.execute('''CREATE TABLE IF NOT EXISTS aset (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama_aset TEXT NOT NULL,
        tanggal_perolehan DATE NOT NULL,
        harga_perolehan REAL NOT NULL,
        nilai_residu REAL DEFAULT 0,
        umur_ekonomis INTEGER NOT NULL,
        metode_penyusutan TEXT NOT NULL,
        akumulasi_penyusutan REAL DEFAULT 0
    )''')
    
    # Tabel persediaan
    c.execute('''CREATE TABLE IF NOT EXISTS persediaan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        jenis_transaksi TEXT NOT NULL,
        jumlah REAL NOT NULL,
        harga_satuan REAL NOT NULL,
        total REAL NOT NULL,
        saldo_jumlah REAL NOT NULL,
        saldo_nilai REAL NOT NULL
    )''')
    
    # Tabel biaya
    c.execute('''CREATE TABLE IF NOT EXISTS biaya (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        kategori_biaya TEXT NOT NULL,
        keterangan TEXT,
        nominal REAL NOT NULL,
        kode_akun TEXT,
        FOREIGN KEY (kode_akun) REFERENCES chart_of_accounts(kode_akun)
    )''')
    
    # Tabel pembelian karyawan
    c.execute('''CREATE TABLE IF NOT EXISTS pembelian_karyawan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        karyawan_id INTEGER,
        jenis_pembelian TEXT NOT NULL,
        nama_item TEXT NOT NULL,
        jumlah REAL NOT NULL,
        harga_satuan REAL NOT NULL,
        total REAL NOT NULL,
        no_nota TEXT,
        FOREIGN KEY (karyawan_id) REFERENCES users(id)
    )''')
    
    # Tabel jurnal penyesuaian
    c.execute('''CREATE TABLE IF NOT EXISTS jurnal_penyesuaian (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tanggal DATE NOT NULL,
        kode_akun TEXT NOT NULL,
        keterangan TEXT,
        debit REAL DEFAULT 0,
        kredit REAL DEFAULT 0,
        FOREIGN KEY (kode_akun) REFERENCES chart_of_accounts(kode_akun)
    )''')
    
    conn.commit()
    return conn

# Fungsi validasi password
def validate_password(password):
    if len(password) < 8 or len(password) > 20:
        return False, "Password harus 8-20 karakter"
    if not re.search(r"[a-z]", password):
        return False, "Password harus mengandung huruf kecil"
    if not re.search(r"[A-Z]", password):
        return False, "Password harus mengandung huruf besar"
    if not re.search(r"[0-9]", password):
        return False, "Password harus mengandung angka"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password harus mengandung karakter khusus"
    return True, "Password valid"

# Fungsi hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Inisialisasi session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Inisialisasi database
conn = init_db()

# Halaman utama
def home_page():
    st.markdown("""
        <style>
        .title {
            text-align: center;
            color: #1E88E5;
            font-size: 72px;
            font-weight: bold;
            margin-bottom: 20px;
        }
        .subtitle {
            text-align: center;
            color: #616161;
            font-size: 24px;
            margin-bottom: 50px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<p class="title">🐟 Tilapia Suite</p>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Sistem Akuntansi Budidaya Ikan Mujair</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Pilih Role Anda")
        
        role_options = {
            "👤 Kasir": "kasir",
            "📊 Akuntan": "akuntan",
            "💼 Owner": "owner",
            "🔧 Karyawan": "karyawan"
        }
        
        selected_role = st.radio(
    "Pilih Role",
    list(role_options.keys()),
    label_visibility="collapsed"
)
        
        st.markdown("---")
        
        col_login, col_register = st.columns(2)
        
        with col_login:
            if st.button("🔐 Login", use_container_width=True, type="primary"):
                st.session_state.page = 'login'
                st.session_state.selected_role = role_options[selected_role]
                st.rerun()
        
        with col_register:
            if st.button("📝 Registrasi", use_container_width=True):
                st.session_state.page = 'register'
                st.session_state.selected_role = role_options[selected_role]
                st.rerun()

# Halaman registrasi
def register_page():
    st.title("📝 Registrasi Akun")

    role = st.session_state.get('selected_role', 'kasir')
    st.info(f"Mendaftar sebagai: **{role.upper()}**")

    email = st.text_input("Email", placeholder="Email")
    username = st.text_input("Username", placeholder="Username") 
    password = st.text_input("Password", type="password", placeholder="Password")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Daftar", type="primary", use_container_width=True):
            if not email or not username or not password:
                st.error("Semua field wajib diisi!")
            else:
                # CEK EMAIL SUDAH ADA
                c = conn.cursor()
                c.execute("SELECT id FROM users WHERE email=?", (email,))
                if c.fetchone():
                    st.error("❌ Email sudah terdaftar!")
                    return
                
                # CEK USERNAME SUDAH ADA  
                c.execute("SELECT id FROM users WHERE username=?", (username,))
                if c.fetchone():
                    st.error("❌ Username sudah terdaftar!")
                    return
                
                # HASH PASSWORD & SIMPAN
                hashed_pw = hash_password(password)
                c.execute(
                    "INSERT INTO users (email, username, password, role, verified) VALUES (?, ?, ?, ?, 1)",
                    (email, username, hashed_pw, role)
                )
                conn.commit()
                
                st.success("✅ Registrasi berhasil! Silakan login.")
                st.balloons()
    
    with col2:
        if st.button("← Kembali ke Home", use_container_width=True):
            st.session_state.page = 'home'
            st.rerun()
                     

# verivy email
def verify_email_page():
    st.title("✅ Verifikasi Email")
    
    # ✅ Ambil token dari query parameters dengan cara yang benar
    query_params = st.query_params
    token = query_params.get("access_token") or query_params.get("token")
    
    if not token:
        st.error("Token verifikasi tidak valid atau sudah kadaluarsa")
        if st.button("← Kembali ke Login"):
            st.session_state.page = 'login'
            st.rerun()
        return
    
    try:
        # ✅ Verify dengan menggunakan access token
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers=headers
        )
        
        if response.status_code == 200:
            user_data = response.json()
            email = user_data.get("email")
            
            if email:
                # Update status di SQLite
                c = conn.cursor()
                c.execute("UPDATE users SET verified=1, verification_token=NULL WHERE email=?", (email,))
                conn.commit()
                
                st.success("✅ Email berhasil diverifikasi! Akun Anda sekarang aktif.")
                st.balloons()
                
                if st.button("🔐 Login Sekarang", type="primary"):
                    st.session_state.page = 'login'
                    st.rerun()
            else:
                st.error("Tidak dapat menemukan informasi user")
        else:
            st.error("Token verifikasi tidak valid atau sudah kadaluarsa")
            
    except Exception as e:
        st.error(f"Error verifikasi: {str(e)}")
    
    if st.button("← Kembali ke Login"):
        st.session_state.page = 'login'
        st.rerun()

# Halaman login
def login_page():
    st.title("🔓 Login")
    
    role = st.session_state.get('selected_role', 'kasir')
    st.info(f"Login sebagai: **{role.upper()}**")
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            submit = st.form_submit_button("Login", type="primary", use_container_width=True)
        with col2:
            forgot = st.form_submit_button("Lupa Password?", use_container_width=True)
        
        if submit:
            if not email or not password:
                st.error("Email dan password harus diisi!")
            else:
                try:
                    # Login ke Supabase
                    auth_response = supabase_login(email, password)
                    user_data = auth_response.get("user")

                    # ✅ Cek login sukses
                    if auth_response.get("access_token") and user_data:
                        st.session_state["user"] = user_data

                        # Cek role di SQLite
                        c = conn.cursor()
                        c.execute(
                            "SELECT id, username, role FROM users WHERE email=? AND role=?",
                            (email, role)
                        )
                        user = c.fetchone()
                        
                        if user:
                            st.session_state.logged_in = True
                            st.session_state.user_id = user[0]
                            st.session_state.username = user[1]
                            st.session_state.role = user[2]
                            st.success(f"Selamat datang, {user[1]}!")
                            st.rerun()
                        else:
                            st.error(f"Akun tidak terdaftar sebagai {role}")
                    else:
                        st.error("❌ Email atau password salah.")

                except Exception as e:
                    st.error(f"Login gagal: {str(e)}")
        
        if forgot:
            st.session_state.page = 'forgot_password'
            st.rerun()
    
    if st.button("← Kembali ke Home"):
        st.session_state.page = 'home'
        st.rerun()
# Halaman lupa password
def verify_page():
    st.title("✅ Verifikasi Akun")

    email = st.session_state.get("pending_email", "")
    token = st.session_state.get("pending_token", "")

    if not email or not token:
        st.error("Token tidak ditemukan! Silakan daftar ulang.")
        return

    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email=? AND verification_token=? AND verified=0", (email, token))
    user = c.fetchone()

    if not user:
        st.error("❌ Link verifikasi tidak valid atau sudah digunakan!")
        return

    st.success(f"Email: **{email}** terverifikasi! Silakan buat username & password.")

    username = st.text_input("Username", placeholder="Username", label_visibility="collapsed")
    password = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
    confirm = st.text_input("Konfirmasi Password", type="password", placeholder="Konfirmasi Password", label_visibility="collapsed")

    if st.button("Selesaikan Registrasi", type="primary"):
        if not username or not password:
            st.error("Semua field harus diisi!")
        elif password != confirm:
            st.error("Password tidak sama!")
        else:
            hashed_pw = hash_password(password)

            c.execute("""
                UPDATE users 
                SET username=?, password=?, verified=1, verification_token=NULL
                WHERE id=?
            """, (username, hashed_pw, user[0]))
            conn.commit()

            st.success("🎉 Akun berhasil dibuat! Silakan login.")
            st.balloons()
            st.session_state.page = "login"
            st.rerun()

# fungsi forgot pw
def forgot_password_page():
    st.title("🔒 Lupa Password")
    
    email = st.text_input("Masukkan Email Anda")
    
    if st.button("Reset Password", type="primary"):
        if not email:
            st.error("Email harus diisi!")
        else:
            c = conn.cursor()
            c.execute("SELECT id FROM users WHERE email=?", (email,))
            if not c.fetchone():
                st.error("❌ Email tidak terdaftar!")
            else:
                # Generate password baru
                new_password = "12345678"  # atau random password
                hashed_new = hash_password(new_password)
#reset pw 
def reset_password_page():
    st.title("🔑 Reset Password")

    # ✅ Ambil token dari query parameters atau session state
    query_params = st.query_params
    access_token = st.session_state.get('access_token') or query_params.get("access_token")

    if not access_token:
        st.error("Token reset tidak valid atau sudah kadaluarsa")
        st.info("Silakan request reset password lagi")
        if st.button("← Kembali ke Login"):
            st.session_state.page = 'login'
            st.rerun()
        return

    with st.form("reset_password_form"):
        new_password = st.text_input("Password Baru", type="password")
        confirm_password = st.text_input("Konfirmasi Password Baru", type="password")

        submit = st.form_submit_button("Reset Password", type="primary")

        if submit:
            if not new_password or not confirm_password:
                st.error("Harap isi semua field")
            elif new_password != confirm_password:
                st.error("Password tidak cocok")
            else:
                # Validasi password
                valid, message = validate_password(new_password)
                if not valid:
                    st.error(message)
                else:
                    try:
                        # ✅ Update password di Supabase
                        headers = {
                            "apikey": SUPABASE_KEY,
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }

                        data = {"password": new_password}
                        response = requests.put(
                            f"{SUPABASE_URL}/auth/v1/user",
                            json=data,
                            headers=headers
                        )

                        if response.status_code == 200:
                            # ✅ Update juga di SQLite
                            user_data = response.json()
                            email = user_data.get("email")
                            
                            if email:
                                c = conn.cursor()
                                c.execute("UPDATE users SET password=? WHERE email=?", 
                                         (hash_password(new_password), email))
                                conn.commit()
                            
                            st.success("✅ Password berhasil direset! Silakan login dengan password baru.")
                            
                            # Clear token
                            if 'access_token' in st.session_state:
                                del st.session_state['access_token']
                            
                            if st.button("🔐 Login Sekarang", type="primary"):
                                st.session_state.page = 'login'
                                st.rerun()
                        else:
                            st.error(f"Gagal reset password: {response.json().get('message', 'Unknown error')}")

                    except Exception as e:
                        st.error(f"Error: {str(e)}")

    if st.button("← Kembali ke Login"):
        st.session_state.page = 'login'
        st.rerun()
               

# Fungsi Jurnal Penyesuaian
def jurnal_penyesuaian():
    st.subheader("📝 Jurnal Penyesuaian")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal Penyesuaian", "Tambah Penyesuaian"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT j.id, j.tanggal, j.kode_akun, c.nama_akun, j.keterangan, j.debit, j.kredit
                     FROM jurnal_penyesuaian j
                     LEFT JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                     ORDER BY j.tanggal DESC, j.id""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'Kode Akun', 'Nama Akun', 'Keterangan', 'Debit', 'Kredit'])
            df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            st.markdown("---")
            id_hapus = st.selectbox("Pilih jurnal untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Jurnal", type="primary"):
                c.execute("DELETE FROM jurnal_penyesuaian WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Jurnal penyesuaian berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada jurnal penyesuaian")
    
    with tab2:
        with st.form("tambah_penyesuaian"):
            tanggal = st.date_input("Tanggal")
            
            c = conn.cursor()
            c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts ORDER BY kode_akun")
            akun_list = c.fetchall()
            
            if not akun_list:
                st.warning("Belum ada Chart of Accounts")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Debit**")
                    akun_debit = st.selectbox("Akun Debit", [f"{x[0]} - {x[1]}" for x in akun_list], key="debit_adj")
                    kode_debit = akun_debit.split(" - ")[0]
                    nominal_debit = st.number_input("Nominal Debit", min_value=0.0, step=1000.0)
                
                with col2:
                    st.markdown("**Kredit**")
                    akun_kredit = st.selectbox("Akun Kredit", [f"{x[0]} - {x[1]}" for x in akun_list], key="kredit_adj")
                    kode_kredit = akun_kredit.split(" - ")[0]
                    nominal_kredit = st.number_input("Nominal Kredit", min_value=0.0, step=1000.0)
                
                keterangan = st.text_area("Keterangan Penyesuaian")
                
                submit = st.form_submit_button("💾 Simpan", type="primary")
                
                if submit:
                    if nominal_debit != nominal_kredit:
                        st.error("Debit dan kredit harus sama!")
                    elif nominal_debit == 0:
                        st.error("Nominal harus lebih dari 0!")
                    else:
                        c.execute("""INSERT INTO jurnal_penyesuaian (tanggal, kode_akun, keterangan, debit, kredit)
                                    VALUES (?, ?, ?, ?, ?)""",
                                 (tanggal, kode_debit, keterangan, nominal_debit, 0))
                        c.execute("""INSERT INTO jurnal_penyesuaian (tanggal, kode_akun, keterangan, debit, kredit)
                                    VALUES (?, ?, ?, ?, ?)""",
                                 (tanggal, kode_kredit, keterangan, 0, nominal_kredit))
                        conn.commit()
                        st.success("Jurnal penyesuaian berhasil dicatat!")
                        st.rerun()

def neraca_saldo():
    st.subheader("⚖️ Neraca Saldo Setelah Penyesuaian")
    
    periode = st.text_input("Periode", value="2024-12")
    
    c = conn.cursor()
    
    # Ambil semua akun
    c.execute("SELECT kode_akun, nama_akun, kategori FROM chart_of_accounts ORDER BY kode_akun")
    akun_list = c.fetchall()
    
    if not akun_list:
        st.warning("Belum ada Chart of Accounts")
        return
    
    data_neraca = []
    
    for akun in akun_list:
        kode_akun = akun[0]
        nama_akun = akun[1]
        kategori = akun[2]
        
        # Saldo awal
        c.execute("SELECT debit, kredit FROM neraca_saldo_awal WHERE kode_akun=? AND periode LIKE ?", 
                 (kode_akun, periode[:4] + "%"))
        saldo_awal = c.fetchone()
        saldo = (saldo_awal[0] - saldo_awal[1]) if saldo_awal else 0
        
        # Transaksi dari jurnal umum
        c.execute("SELECT SUM(debit), SUM(kredit) FROM jurnal_umum WHERE kode_akun=?", (kode_akun,))
        ju = c.fetchone()
        if ju[0]:
            saldo += (ju[0] - ju[1])
        
        # Transaksi dari jurnal penyesuaian
        c.execute("SELECT SUM(debit), SUM(kredit) FROM jurnal_penyesuaian WHERE kode_akun=?", (kode_akun,))
        jp = c.fetchone()
        if jp[0]:
            saldo += (jp[0] - jp[1])
        
        # Khusus akun kas - dari jurnal khusus
        if "kas" in nama_akun.lower() or "1-1010" in kode_akun:
            c.execute("SELECT SUM(debit_kas) FROM jurnal_penjualan")
            jp_kas = c.fetchone()
            if jp_kas[0]:
                saldo += jp_kas[0]
            
            c.execute("SELECT SUM(kredit_kas) FROM jurnal_pembelian")
            jb_kas = c.fetchone()
            if jb_kas[0]:
                saldo -= jb_kas[0]
            
            c.execute("SELECT SUM(debit_kas) FROM jurnal_penerimaan_kas")
            jt_kas = c.fetchone()
            if jt_kas[0]:
                saldo += jt_kas[0]
            
            c.execute("SELECT SUM(kredit_kas) FROM jurnal_pengeluaran_kas")
            jk_kas = c.fetchone()
            if jk_kas[0]:
                saldo -= jk_kas[0]
        
        if abs(saldo) > 0.01:  # Hanya tampilkan akun dengan saldo
            if saldo >= 0:
                data_neraca.append({
                    'Kode Akun': kode_akun,
                    'Nama Akun': nama_akun,
                    'Kategori': kategori,
                    'Debit': saldo,
                    'Kredit': 0
                })
            else:
                data_neraca.append({
                    'Kode Akun': kode_akun,
                    'Nama Akun': nama_akun,
                    'Kategori': kategori,
                    'Debit': 0,
                    'Kredit': abs(saldo)
                })
    
    if data_neraca:
        df = pd.DataFrame(data_neraca)
        df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
        df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
        
        st.dataframe(df, use_container_width=True)
        
        # Total
        total_debit = sum([x['Debit'] if isinstance(x['Debit'], (int, float)) else 0 for x in data_neraca])
        total_kredit = sum([x['Kredit'] if isinstance(x['Kredit'], (int, float)) else 0 for x in data_neraca])
        
        col1, col2 = st.columns(2)
        col1.metric("Total Debit", f"Rp {total_debit:,.0f}")
        col2.metric("Total Kredit", f"Rp {total_kredit:,.0f}")
        
        if abs(total_debit - total_kredit) < 1:
            st.success("✅ Neraca Saldo Seimbang!")
        else:
            st.error(f"⚠️ Neraca Tidak Seimbang! Selisih: Rp {abs(total_debit - total_kredit):,.0f}")
    else:
        st.info("Belum ada data untuk neraca saldo")

def jurnal_penutup():
    st.subheader("🔒 Jurnal Penutup")
    
    st.info("Jurnal penutup digunakan untuk menutup akun nominal (pendapatan dan beban) ke Ikhtisar Laba Rugi")
    
    tab1, tab2 = st.tabs(["Generate Jurnal Penutup", "Lihat Jurnal Penutup"])
    
    with tab1:
        periode = st.text_input("Periode Penutupan", value="2024-12-31")
        
        if st.button("🔄 Generate Jurnal Penutup", type="primary"):
            c = conn.cursor()
            
            # Tutup pendapatan
            c.execute("""SELECT kode_akun, SUM(kredit) - SUM(debit) as saldo
                         FROM jurnal_umum 
                         WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Pendapatan')
                         GROUP BY kode_akun""")
            pendapatan = c.fetchall()
            
            # Tutup beban
            c.execute("""SELECT kode_akun, SUM(debit) - SUM(kredit) as saldo
                         FROM jurnal_umum 
                         WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Beban')
                         GROUP BY kode_akun""")
            beban = c.fetchall()
            
            total_pendapatan = sum([x[1] for x in pendapatan])
            total_beban = sum([x[1] for x in beban])
            laba_rugi = total_pendapatan - total_beban
            
            st.markdown(f"""
            ### Ringkasan:
            - Total Pendapatan: Rp {total_pendapatan:,.0f}
            - Total Beban: Rp {total_beban:,.0f}
            - Laba/Rugi: Rp {laba_rugi:,.0f} {'(Laba)' if laba_rugi > 0 else '(Rugi)'}
            """)
            
            # Simpan jurnal penutup
            # 1. Tutup pendapatan
            for p in pendapatan:
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, p[0], "Jurnal Penutup - Menutup Pendapatan", p[1], 0, "JCP"))
            
            c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (periode, '3-1020', "Jurnal Penutup - Ikhtisar L/R", 0, total_pendapatan, "JCP"))
            
            # 2. Tutup beban
            c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                     (periode, '3-1020', "Jurnal Penutup - Ikhtisar L/R", total_beban, 0, "JCP"))
            
            for b in beban:
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, b[0], "Jurnal Penutup - Menutup Beban", 0, b[1], "JCP"))
            
            # 3. Tutup ikhtisar L/R ke modal
            if laba_rugi > 0:
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, '3-1020', "Jurnal Penutup - Tutup Laba ke Modal", laba_rugi, 0, "JCP"))
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, '3-1010', "Jurnal Penutup - Tutup Laba ke Modal", 0, laba_rugi, "JCP"))
            else:
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, '3-1010', "Jurnal Penutup - Tutup Rugi ke Modal", abs(laba_rugi), 0, "JCP"))
                c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (periode, '3-1020', "Jurnal Penutup - Tutup Rugi ke Modal", 0, abs(laba_rugi), "JCP"))
            
            conn.commit()
            st.success("✅ Jurnal penutup berhasil dibuat!")
            st.rerun()
    
    with tab2:
        c = conn.cursor()
        c.execute("""SELECT j.tanggal, j.kode_akun, c.nama_akun, j.keterangan, j.debit, j.kredit
                     FROM jurnal_umum j
                     LEFT JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                     WHERE j.ref = 'JCP'
                     ORDER BY j.tanggal DESC, j.id""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Kode Akun', 'Nama Akun', 'Keterangan', 'Debit', 'Kredit'])
            df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Belum ada jurnal penutup")

def jurnal_pembalik():
    st.subheader("🔄 Jurnal Pembalik")
    
    st.info("Jurnal pembalik dibuat di awal periode untuk membalik jurnal penyesuaian tertentu")
    
    tab1, tab2 = st.tabs(["Generate Jurnal Pembalik", "Lihat Jurnal Pembalik"])
    
    with tab1:
        st.markdown("### Pilih Jurnal Penyesuaian untuk Dibalik")
        
        c = conn.cursor()
        c.execute("""SELECT j.id, j.tanggal, j.kode_akun, c.nama_akun, j.keterangan, j.debit, j.kredit
                     FROM jurnal_penyesuaian j
                     LEFT JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                     ORDER BY j.tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'Kode Akun', 'Nama Akun', 'Keterangan', 'Debit', 'Kredit'])
            
            for col in ['Debit', 'Kredit']:
                df[col] = df[col].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            id_pembalik = st.multiselect("Pilih ID jurnal yang akan dibalik", df['ID'].tolist())
            tanggal_pembalik = st.date_input("Tanggal Jurnal Pembalik", value=datetime.now().date())
            
            if st.button("🔄 Buat Jurnal Pembalik", type="primary"):
                if not id_pembalik:
                    st.error("Pilih minimal satu jurnal untuk dibalik!")
                else:
                    for id_val in id_pembalik:
                        c.execute("""SELECT kode_akun, keterangan, debit, kredit FROM jurnal_penyesuaian WHERE id=?""", 
                                 (id_val,))
                        jurnal = c.fetchone()
                        
                        # Balik debit-kredit
                        c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                 (tanggal_pembalik, jurnal[0], f"Jurnal Pembalik - {jurnal[1]}", 
                                  jurnal[3], jurnal[2], "JPB"))
                    
                    conn.commit()
                    st.success("✅ Jurnal pembalik berhasil dibuat!")
                    st.rerun()
        else:
            st.info("Belum ada jurnal penyesuaian untuk dibalik")
    
    with tab2:
        c = conn.cursor()
        c.execute("""SELECT j.tanggal, j.kode_akun, c.nama_akun, j.keterangan, j.debit, j.kredit
                     FROM jurnal_umum j
                     LEFT JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                     WHERE j.ref = 'JPB'
                     ORDER BY j.tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Kode Akun', 'Nama Akun', 'Keterangan', 'Debit', 'Kredit'])
            df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Belum ada jurnal pembalik")

def laporan_keuangan():
    st.subheader("📊 Laporan Keuangan")
    
    jenis_laporan = st.selectbox("Pilih Laporan", 
                                ["Laporan Laba Rugi", "Laporan Perubahan Modal", "Neraca"])
    
    if jenis_laporan == "Laporan Laba Rugi":
        laporan_laba_rugi()
    elif jenis_laporan == "Laporan Perubahan Modal":
        laporan_perubahan_modal()
    elif jenis_laporan == "Neraca":
        laporan_neraca()

def laporan_laba_rugi():
    st.markdown("### 📈 Laporan Laba Rugi")
    
    col1, col2 = st.columns(2)
    tanggal_awal = col1.date_input("Dari Tanggal", value=datetime(2024, 1, 1).date())
    tanggal_akhir = col2.date_input("Sampai Tanggal", value=datetime.now().date())
    
    c = conn.cursor()
    
    # Pendapatan
    c.execute("""SELECT c.nama_akun, SUM(j.kredit) - SUM(j.debit) as saldo
                 FROM jurnal_umum j
                 JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                 WHERE c.kategori = 'Pendapatan' AND j.tanggal BETWEEN ? AND ?
                 GROUP BY j.kode_akun, c.nama_akun""", (tanggal_awal, tanggal_akhir))
    pendapatan = c.fetchall()
    
    # Tambah dari jurnal penjualan
    c.execute("SELECT SUM(kredit_penjualan) FROM jurnal_penjualan WHERE tanggal BETWEEN ? AND ?", 
             (tanggal_awal, tanggal_akhir))
    penjualan = c.fetchone()
    
    total_pendapatan = sum([x[1] for x in pendapatan]) + (penjualan[0] if penjualan[0] else 0)
    
    # HPP
    c.execute("SELECT SUM(debit_hpp) FROM jurnal_penjualan WHERE tanggal BETWEEN ? AND ?", 
             (tanggal_awal, tanggal_akhir))
    hpp = c.fetchone()
    total_hpp = hpp[0] if hpp[0] else 0
    
    laba_kotor = total_pendapatan - total_hpp
    
    # Beban
    c.execute("""SELECT c.nama_akun, SUM(j.debit) - SUM(j.kredit) as saldo
                 FROM jurnal_umum j
                 JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                 WHERE c.kategori = 'Beban' AND j.tanggal BETWEEN ? AND ?
                 GROUP BY j.kode_akun, c.nama_akun""", (tanggal_awal, tanggal_akhir))
    beban = c.fetchall()
    
    total_beban = sum([x[1] for x in beban])
    laba_bersih = laba_kotor - total_beban
    
    # Tampilkan laporan
    st.markdown(f"""
    ---
    ### TILAPIA SUITE
    ### LAPORAN LABA RUGI
    ### Periode {tanggal_awal.strftime('%d %B %Y')} s/d {tanggal_akhir.strftime('%d %B %Y')}
    ---
    
    **PENDAPATAN:**
    """)
    
    for p in pendapatan:
        st.markdown(f"- {p[0]}: Rp {p[1]:,.0f}")
    if penjualan[0]:
        st.markdown(f"- Penjualan: Rp {penjualan[0]:,.0f}")
    
    st.markdown(f"""
    **Total Pendapatan: Rp {total_pendapatan:,.0f}**
    
    **HARGA POKOK PENJUALAN:**
    - HPP: Rp {total_hpp:,.0f}
    
    **LABA KOTOR: Rp {laba_kotor:,.0f}**
    
    **BEBAN OPERASIONAL:**
    """)
    
    for b in beban:
        st.markdown(f"- {b[0]}: Rp {b[1]:,.0f}")
    
    st.markdown(f"""
    **Total Beban: Rp {total_beban:,.0f}**
    
    ---
    
    ## **LABA/RUGI BERSIH: Rp {laba_bersih:,.0f}**
    
    ---
    """)
    
    # Grafik
    st.markdown("### 📊 Visualisasi")
    
    col1, col2 = st.columns(2)
    
    with col1:
        data_pie = pd.DataFrame({
            'Kategori': ['Pendapatan', 'HPP', 'Beban'],
            'Nilai': [total_pendapatan, total_hpp, total_beban]
        })
        fig = px.pie(data_pie, values='Nilai', names='Kategori', title='Komposisi L/R')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        data_bar = pd.DataFrame({
            'Kategori': ['Pendapatan', 'Laba Kotor', 'Laba Bersih'],
            'Nilai': [total_pendapatan, laba_kotor, laba_bersih]
        })
        fig = px.bar(data_bar, x='Kategori', y='Nilai', title='Perbandingan Pendapatan & Laba')
        st.plotly_chart(fig, use_container_width=True)

def laporan_perubahan_modal():
    st.markdown("### 💰 Laporan Perubahan Modal")
    
    periode = st.text_input("Periode", value="2024")
    
    c = conn.cursor()
    
    # Modal awal
    c.execute("""SELECT SUM(kredit) - SUM(debit) as modal
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Ekuitas')
                 AND tanggal < ?""", (f"{periode}-01-01",))
    modal_awal = c.fetchone()
    modal_awal_nilai = modal_awal[0] if modal_awal and modal_awal[0] else 0
    
    # Laba/Rugi periode berjalan
    c.execute("""SELECT SUM(kredit) - SUM(debit) as pendapatan
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Pendapatan')
                 AND tanggal LIKE ?""", (f"{periode}%",))
    pendapatan = c.fetchone()
    total_pendapatan = pendapatan[0] if pendapatan and pendapatan[0] else 0
    
    c.execute("""SELECT SUM(debit) - SUM(kredit) as beban
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Beban')
                 AND tanggal LIKE ?""", (f"{periode}%",))
    beban = c.fetchone()
    total_beban = beban[0] if beban and beban[0] else 0
    
    laba_rugi = total_pendapatan - total_beban
    
    # Prive (jika ada)
    c.execute("""SELECT SUM(debit) as prive
                 FROM jurnal_umum
                 WHERE kode_akun LIKE '%prive%' AND tanggal LIKE ?""", (f"{periode}%",))
    prive = c.fetchone()
    total_prive = prive[0] if prive and prive[0] else 0
    
    modal_akhir = modal_awal_nilai + laba_rugi - total_prive
    
    st.markdown(f"""
    ---
    ### TILAPIA SUITE
    ### LAPORAN PERUBAHAN MODAL
    ### Periode Tahun {periode}
    ---
    
    | Keterangan | Jumlah (Rp) |
    |------------|-------------|
    | Modal Awal | {modal_awal_nilai:,.0f} |
    | Laba/Rugi Bersih | {laba_rugi:,.0f} |
    | Prive | ({total_prive:,.0f}) |
    | **Modal Akhir** | **{modal_akhir:,.0f}** |
    
    ---
    """)
    
    # Grafik
    data = pd.DataFrame({
        'Komponen': ['Modal Awal', 'Laba Bersih', 'Prive', 'Modal Akhir'],
        'Nilai': [modal_awal_nilai, laba_rugi, -total_prive, modal_akhir]
    })
    
    fig = go.Figure(data=[
        go.Waterfall(
            x=data['Komponen'],
            y=data['Nilai'],
            text=[f"Rp {abs(v):,.0f}" for v in data['Nilai']],
            textposition="outside",
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    ])
    fig.update_layout(title="Waterfall Chart - Perubahan Modal", showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def laporan_neraca():
    st.markdown("### 📋 Neraca")
    
    tanggal_neraca = st.date_input("Per Tanggal", value=datetime.now().date())
    
    c = conn.cursor()
    
    # ASET
    st.markdown("## ASET")
    
    # Aset Lancar
    st.markdown("### Aset Lancar")
    aset_lancar = []
    
    # Kas
    c.execute("""SELECT SUM(debit) - SUM(kredit) as saldo
                 FROM jurnal_umum
                 WHERE kode_akun LIKE '1-1010%' AND tanggal <= ?""", (tanggal_neraca,))
    kas = c.fetchone()
    kas_saldo = kas[0] if kas and kas[0] else 0
    
    # Tambah dari jurnal khusus
    c.execute("SELECT SUM(debit_kas) FROM jurnal_penjualan WHERE tanggal <= ?", (tanggal_neraca,))
    kas_jp = c.fetchone()
    kas_saldo += kas_jp[0] if kas_jp[0] else 0
    
    c.execute("SELECT SUM(kredit_kas) FROM jurnal_pembelian WHERE tanggal <= ?", (tanggal_neraca,))
    kas_jb = c.fetchone()
    kas_saldo -= kas_jb[0] if kas_jb[0] else 0
    
    aset_lancar.append(('Kas', kas_saldo))
    
    # Piutang (jika ada)
    c.execute("""SELECT SUM(debit) - SUM(kredit) as saldo
                 FROM jurnal_umum
                 WHERE kode_akun LIKE '1-1020%' AND tanggal <= ?""", (tanggal_neraca,))
    piutang = c.fetchone()
    piutang_saldo = piutang[0] if piutang and piutang[0] else 0
    if piutang_saldo > 0:
        aset_lancar.append(('Piutang', piutang_saldo))
    
    # Persediaan
    c.execute("SELECT saldo_nilai FROM persediaan ORDER BY id DESC LIMIT 1")
    persediaan = c.fetchone()
    persediaan_saldo = persediaan[0] if persediaan else 0
    aset_lancar.append(('Persediaan', persediaan_saldo))
    
    total_aset_lancar = sum([x[1] for x in aset_lancar])
    
    for item in aset_lancar:
        st.markdown(f"- {item[0]}: Rp {item[1]:,.0f}")
    st.markdown(f"**Total Aset Lancar: Rp {total_aset_lancar:,.0f}**")
    
    # Aset Tetap
    st.markdown("### Aset Tetap")
    aset_tetap = []
    
    c.execute("""SELECT nama_aset, harga_perolehan, akumulasi_penyusutan, 
                        (harga_perolehan - akumulasi_penyusutan) as nilai_buku
                 FROM aset""")
    aset_data = c.fetchall()
    
    total_aset_tetap_kotor = 0
    total_akum_penyusutan = 0
    
    for aset in aset_data:
        st.markdown(f"- {aset[0]}: Rp {aset[1]:,.0f}")
        total_aset_tetap_kotor += aset[1]
        total_akum_penyusutan += aset[2]
    
    st.markdown(f"- Akumulasi Penyusutan: (Rp {total_akum_penyusutan:,.0f})")
    total_aset_tetap = total_aset_tetap_kotor - total_akum_penyusutan
    st.markdown(f"**Total Aset Tetap: Rp {total_aset_tetap:,.0f}**")
    
    total_aset = total_aset_lancar + total_aset_tetap
    st.markdown(f"## **TOTAL ASET: Rp {total_aset:,.0f}**")
    
    st.markdown("---")
    
    # LIABILITAS
    st.markdown("## LIABILITAS")
    
    c.execute("""SELECT c.nama_akun, SUM(j.kredit) - SUM(j.debit) as saldo
                 FROM jurnal_umum j
                 JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                 WHERE c.kategori = 'Liabilitas' AND j.tanggal <= ?
                 GROUP BY j.kode_akun, c.nama_akun""", (tanggal_neraca,))
    liabilitas = c.fetchall()
    
    total_liabilitas = 0
    for item in liabilitas:
        if item[1] > 0:
            st.markdown(f"- {item[0]}: Rp {item[1]:,.0f}")
            total_liabilitas += item[1]
    
    if total_liabilitas == 0:
        st.markdown("- Tidak ada liabilitas")
    
    st.markdown(f"## **TOTAL LIABILITAS: Rp {total_liabilitas:,.0f}**")
    
    st.markdown("---")
    
    # EKUITAS
    st.markdown("## EKUITAS")
    
    # Modal awal
    c.execute("""SELECT SUM(kredit) - SUM(debit) as modal
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Ekuitas')
                 AND tanggal <= ?""", (tanggal_neraca,))
    modal = c.fetchone()
    modal_saldo = modal[0] if modal and modal[0] else 0
    
    # Laba/Rugi berjalan
    c.execute("""SELECT SUM(kredit) - SUM(debit) as pendapatan
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Pendapatan')
                 AND tanggal <= ?""", (tanggal_neraca,))
    pendapatan = c.fetchone()
    total_pendapatan = pendapatan[0] if pendapatan and pendapatan[0] else 0
    
    c.execute("""SELECT SUM(debit) - SUM(kredit) as beban
                 FROM jurnal_umum
                 WHERE kode_akun IN (SELECT kode_akun FROM chart_of_accounts WHERE kategori='Beban')
                 AND tanggal <= ?""", (tanggal_neraca,))
    beban = c.fetchone()
    total_beban = beban[0] if beban and beban[0] else 0
    
    laba_rugi = total_pendapatan - total_beban
    
    st.markdown(f"- Modal: Rp {modal_saldo:,.0f}")
    st.markdown(f"- Laba/Rugi Berjalan: Rp {laba_rugi:,.0f}")
    
    total_ekuitas = modal_saldo + laba_rugi
    st.markdown(f"## **TOTAL EKUITAS: Rp {total_ekuitas:,.0f}**")
    
    st.markdown("---")
    
    total_pasiva = total_liabilitas + total_ekuitas
    st.markdown(f"## **TOTAL LIABILITAS & EKUITAS: Rp {total_pasiva:,.0f}**")
    
    # Check balance
    if abs(total_aset - total_pasiva) < 1:
        st.success("✅ Neraca Seimbang!")
    else:
        st.error(f"⚠️ Neraca Tidak Seimbang! Selisih: Rp {abs(total_aset - total_pasiva):,.0f}")
    
    # Grafik
    st.markdown("---")
    st.markdown("### 📊 Visualisasi Neraca")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Komposisi Aset
        data_aset = pd.DataFrame({
            'Kategori': ['Aset Lancar', 'Aset Tetap'],
            'Nilai': [total_aset_lancar, total_aset_tetap]
        })
        fig = px.pie(data_aset, values='Nilai', names='Kategori', title='Komposisi Aset')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Komposisi Pasiva
        data_pasiva = pd.DataFrame({
            'Kategori': ['Liabilitas', 'Ekuitas'],
            'Nilai': [total_liabilitas, total_ekuitas]
        })
        fig = px.pie(data_pasiva, values='Nilai', names='Kategori', title='Komposisi Liabilitas & Ekuitas')
        st.plotly_chart(fig, use_container_width=True)

# Dashboard Karyawan
def karyawan_dashboard():
    st.title("🔧 Dashboard Karyawan")
    
    with st.sidebar:
        st.markdown(f"### Halo, {st.session_state.username}!")
        st.markdown("**Role:** Karyawan")
        
        menu = st.radio("Menu", ["Pembelian Benih", "Pembelian Pakan & Supplies", "Riwayat Pembelian", "Pengaturan Akun"])
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if menu == "Pembelian Benih":
        karyawan_pembelian_benih()
    elif menu == "Pembelian Pakan & Supplies":
        karyawan_pembelian_supplies()
    elif menu == "Riwayat Pembelian":
        karyawan_riwayat()
    elif menu == "Pengaturan Akun":
        pengaturan_akun()

def karyawan_pembelian_benih():
    st.subheader("🐟 Pembelian Benih")
    
    with st.form("pembelian_benih"):
        tanggal = st.date_input("Tanggal Pembelian")
        nama_benih = st.text_input("Jenis Benih", value="Benih Ikan Mujair")
        jumlah = st.number_input("Jumlah (ekor)", min_value=0, step=100)
        harga_satuan = st.number_input("Harga per Ekor (Rp)", min_value=0.0, step=100.0)
        supplier = st.text_input("Nama Supplier")
        no_nota = st.text_input("No. Nota")
        
        submit = st.form_submit_button("💾 Simpan Pembelian", type="primary")
        
        if submit:
            if not nama_benih or jumlah == 0:
                st.error("Semua field harus diisi dengan benar!")
            else:
                total = jumlah * harga_satuan
                
                c = conn.cursor()
                # Simpan ke tabel pembelian karyawan
                c.execute("""INSERT INTO pembelian_karyawan 
                            (tanggal, karyawan_id, jenis_pembelian, nama_item, jumlah, harga_satuan, total, no_nota)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (tanggal, st.session_state.user_id, "Benih", nama_benih, jumlah, harga_satuan, total, no_nota))
                
                # Auto posting ke jurnal pembelian
                c.execute("""INSERT INTO jurnal_pembelian 
                            (tanggal, no_faktur, keterangan, debit_pembelian, kredit_kas, debit_persediaan)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (tanggal, no_nota, f"Pembelian {nama_benih} {jumlah} ekor dari {supplier}", 
                          total, total, total))
                
                # Update persediaan
                c.execute("SELECT saldo_jumlah, saldo_nilai FROM persediaan ORDER BY id DESC LIMIT 1")
                last_saldo = c.fetchone()
                
                if last_saldo:
                    new_qty = last_saldo[0] + jumlah
                    new_nilai = last_saldo[1] + total
                else:
                    new_qty = jumlah
                    new_nilai = total
                
                c.execute("""INSERT INTO persediaan 
                            (tanggal, jenis_transaksi, jumlah, harga_satuan, total, saldo_jumlah, saldo_nilai)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (tanggal, "Pembelian", jumlah, harga_satuan, total, new_qty, new_nilai))
                
                conn.commit()
                
                st.success(f"✅ Pembelian {nama_benih} sebanyak {jumlah} ekor berhasil dicatat!")
                st.info(f"Total: Rp {total:,.0f}")
                st.rerun()

def karyawan_pembelian_supplies():
    st.subheader("📦 Pembelian Pakan & Supplies")
    
    with st.form("pembelian_supplies"):
        tanggal = st.date_input("Tanggal Pembelian")
        
        jenis_item = st.selectbox("Jenis Item", [
            "Pakan Ikan",
            "Obat-obatan",
            "Alat Perawatan",
            "Vitamin",
            "Lain-lain"
        ])
        
        nama_item = st.text_input("Nama Item")
        jumlah = st.number_input("Jumlah", min_value=0.0, step=1.0)
        satuan = st.text_input("Satuan (kg, liter, pcs, dll)", value="kg")
        harga_satuan = st.number_input("Harga Satuan (Rp)", min_value=0.0, step=1000.0)
        supplier = st.text_input("Nama Supplier")
        no_nota = st.text_input("No. Nota")
        
        submit = st.form_submit_button("💾 Simpan Pembelian", type="primary")
        
        if submit:
            if not nama_item or jumlah == 0:
                st.error("Semua field harus diisi dengan benar!")
            else:
                total = jumlah * harga_satuan
                
                c = conn.cursor()
                # Simpan ke tabel pembelian karyawan
                c.execute("""INSERT INTO pembelian_karyawan 
                            (tanggal, karyawan_id, jenis_pembelian, nama_item, jumlah, harga_satuan, total, no_nota)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (tanggal, st.session_state.user_id, jenis_item, f"{nama_item} ({satuan})", 
                          jumlah, harga_satuan, total, no_nota))
                
                # Auto posting ke biaya
                c.execute("""INSERT INTO biaya (tanggal, kategori_biaya, keterangan, nominal, kode_akun)
                            VALUES (?, ?, ?, ?, ?)""",
                         (tanggal, f"Biaya {jenis_item}", 
                          f"Pembelian {nama_item} {jumlah} {satuan} dari {supplier}", total, "5-1020"))
                
                # Auto posting ke jurnal pengeluaran kas
                c.execute("""INSERT INTO jurnal_pengeluaran_kas 
                            (tanggal, no_bukti, keterangan, debit_akun, debit_nominal, kredit_kas)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (tanggal, no_nota, f"Pembelian {nama_item}", "5-1020", total, total))
                
                conn.commit()
                
                st.success(f"✅ Pembelian {nama_item} sebanyak {jumlah} {satuan} berhasil dicatat!")
                st.info(f"Total: Rp {total:,.0f}")
                st.rerun()

def karyawan_riwayat():
    st.subheader("📜 Riwayat Pembelian")
    
    c = conn.cursor()
    c.execute("""SELECT tanggal, jenis_pembelian, nama_item, jumlah, harga_satuan, total, no_nota
                 FROM pembelian_karyawan
                 WHERE karyawan_id = ?
                 ORDER BY tanggal DESC""", (st.session_state.user_id,))
    
    data = c.fetchall()
    
    if data:
        df = pd.DataFrame(data, columns=['Tanggal', 'Jenis', 'Nama Item', 'Jumlah', 'Harga Satuan', 'Total', 'No. Nota'])
        df['Harga Satuan'] = df['Harga Satuan'].apply(lambda x: f"Rp {x:,.0f}")
        df['Total'] = df['Total'].apply(lambda x: f"Rp {x:,.0f}")
        
        st.dataframe(df, use_container_width=True)
        
        # Statistik
        st.markdown("---")
        st.subheader("📊 Statistik Pembelian")
        
        col1, col2, col3 = st.columns(3)
        
        total_pembelian = len(data)
        total_nilai = sum([x[5] for x in data])
        
        col1.metric("Total Transaksi", total_pembelian)
        col2.metric("Total Nilai", f"Rp {total_nilai:,.0f}")
        
        # Grafik per jenis
        c.execute("""SELECT jenis_pembelian, SUM(total) as total
                     FROM pembelian_karyawan
                     WHERE karyawan_id = ?
                     GROUP BY jenis_pembelian""", (st.session_state.user_id,))
        jenis_data = c.fetchall()
        
        if jenis_data:
            df_jenis = pd.DataFrame(jenis_data, columns=['Jenis', 'Total'])
            fig = px.bar(df_jenis, x='Jenis', y='Total', title='Total Pembelian per Jenis')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Belum ada riwayat pembelian")

# Dashboard Owner
def owner_dashboard():
    st.title("💼 Dashboard Owner")
    
    with st.sidebar:
        st.markdown(f"### Halo, {st.session_state.username}!")
        st.markdown("**Role:** Owner")
        
        menu = st.selectbox("Menu", [
            "Dashboard Utama",
            "Laporan Penjualan",
            "Laporan Keuangan",
            "Manajemen User",
            "Database",
            "Pengaturan Akun"
        ])
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if menu == "Dashboard Utama":
        owner_dashboard_main()
    elif menu == "Laporan Penjualan":
        owner_laporan_penjualan()
    elif menu == "Laporan Keuangan":
        laporan_keuangan()
    elif menu == "Manajemen User":
        owner_manajemen_user()
    elif menu == "Database":
        owner_database()
    elif menu == "Pengaturan Akun":
        pengaturan_akun()

def owner_dashboard_main():
    st.subheader("📊 Dashboard Owner - Ringkasan Bisnis")
    
    c = conn.cursor()
    
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    # Total Penjualan
    c.execute("SELECT SUM(total) FROM transaksi_penjualan")
    total_penjualan = c.fetchone()[0] or 0
    col1.metric("💰 Total Penjualan", f"Rp {total_penjualan:,.0f}")
    
    # Total Transaksi
    c.execute("SELECT COUNT(*) FROM transaksi_penjualan")
    total_transaksi = c.fetchone()[0] or 0
    col2.metric("🧾 Total Transaksi", total_transaksi)
    
    # Total Biaya
    c.execute("SELECT SUM(nominal) FROM biaya")
    total_biaya = c.fetchone()[0] or 0
    col3.metric("💸 Total Biaya", f"Rp {total_biaya:,.0f}")
    
    # Laba Bersih
    laba_kotor = total_penjualan * 0.4  # Asumsi margin 40%
    laba_bersih = laba_kotor - total_biaya
    col4.metric("📈 Laba Bersih", f"Rp {laba_bersih:,.0f}")
    
    st.markdown("---")
    
    # Grafik Penjualan
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📈 Trend Penjualan (30 Hari)")
        c.execute("""SELECT tanggal, SUM(total) as total
                     FROM transaksi_penjualan
                     WHERE tanggal >= date('now', '-30 days')
                     GROUP BY tanggal
                     ORDER BY tanggal""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Total'])
            fig = px.area(df, x='Tanggal', y='Total', title='Penjualan Harian')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data penjualan")
    
    with col_chart2:
        st.subheader("🥧 Metode Pembayaran")
        c.execute("""SELECT metode_bayar, SUM(total) as total
                     FROM transaksi_penjualan
                     GROUP BY metode_bayar""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Metode', 'Total'])
            fig = px.pie(df, values='Total', names='Metode')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data pembayaran")
    
    st.markdown("---")
    
    # Performa per Kasir
    st.subheader("👥 Performa Kasir")
    c.execute("""SELECT u.username, COUNT(t.id) as jumlah_transaksi, SUM(t.total) as total_penjualan
                 FROM transaksi_penjualan t
                 JOIN users u ON t.kasir_id = u.id
                 GROUP BY t.kasir_id, u.username
                 ORDER BY total_penjualan DESC""")
    data = c.fetchall()
    
    if data:
        df = pd.DataFrame(data, columns=['Kasir', 'Jumlah Transaksi', 'Total Penjualan'])
        df['Total Penjualan'] = df['Total Penjualan'].apply(lambda x: f"Rp {x:,.0f}")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada data transaksi")

def owner_laporan_penjualan():
    st.subheader("📊 Laporan Penjualan Detail")
    
    tab1, tab2, tab3 = st.tabs(["Per Hari", "Per Bulan", "Per Tahun"])
    
    with tab1:
        tanggal = st.date_input("Pilih Tanggal")
        
        c = conn.cursor()
        c.execute("""SELECT t.no_struk, t.waktu, t.jumlah_kg, t.total, t.metode_bayar, u.username
                     FROM transaksi_penjualan t
                     LEFT JOIN users u ON t.kasir_id = u.id
                     WHERE t.tanggal = ?
                     ORDER BY t.waktu""", (tanggal,))
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['No. Struk', 'Waktu', 'Jumlah (kg)', 'Total', 'Metode', 'Kasir'])
            df['Total'] = df['Total'].apply(lambda x: f"Rp {x:,.0f}")
            st.dataframe(df, use_container_width=True)
            
            total = sum([x[3] for x in data])
            st.metric("Total Penjualan Hari Ini", f"Rp {total:,.0f}")
        else:
            st.info(f"Tidak ada transaksi pada tanggal {tanggal}")
    
    with tab2:
        bulan = st.selectbox("Pilih Bulan", 
                            ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                             "Juli", "Agustus", "September", "Oktober", "November", "Desember"])
        tahun = st.number_input("Tahun", min_value=2020, max_value=2030, value=2024)
        
        bulan_num = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                     "Juli", "Agustus", "September", "Oktober", "November", "Desember"].index(bulan) + 1
        
        c = conn.cursor()
        c.execute("""SELECT tanggal, SUM(total) as total, COUNT(*) as jumlah
                     FROM transaksi_penjualan
                     WHERE strftime('%m', tanggal) = ? AND strftime('%Y', tanggal) = ?
                     GROUP BY tanggal
                     ORDER BY tanggal""", (f"{bulan_num:02d}", str(tahun)))
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Total', 'Jumlah Transaksi'])
            
            fig = px.bar(df, x='Tanggal', y='Total', title=f'Penjualan Harian - {bulan} {tahun}')
            st.plotly_chart(fig, use_container_width=True)
            
            total = sum([x[1] for x in data])
            st.metric(f"Total Penjualan {bulan} {tahun}", f"Rp {total:,.0f}")
        else:
            st.info(f"Tidak ada transaksi pada {bulan} {tahun}")
    
    with tab3:
        tahun_lap = st.number_input("Pilih Tahun", min_value=2020, max_value=2030, value=2024, key="tahun_lap")
        
        c = conn.cursor()
        c.execute("""SELECT strftime('%m', tanggal) as bulan, SUM(total) as total
                     FROM transaksi_penjualan
                     WHERE strftime('%Y', tanggal) = ?
                     GROUP BY bulan
                     ORDER BY bulan""", (str(tahun_lap),))
        data = c.fetchall()
        
        if data:
            bulan_nama = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
            df = pd.DataFrame(data, columns=['Bulan', 'Total'])
            df['Bulan'] = df['Bulan'].apply(lambda x: bulan_nama[int(x)-1])
            
            fig = px.line(df, x='Bulan', y='Total', markers=True, title=f'Trend Penjualan Tahun {tahun_lap}')
            st.plotly_chart(fig, use_container_width=True)
            
            total = sum([x[1] for x in data])
            st.metric(f"Total Penjualan Tahun {tahun_lap}", f"Rp {total:,.0f}")
        else:
            st.info(f"Tidak ada transaksi pada tahun {tahun_lap}")

def owner_manajemen_user():
    st.subheader("👥 Manajemen User")
    
    c = conn.cursor()
    c.execute("""SELECT id, email, username, role, verified, nama_lengkap, no_telepon
                 FROM users
                 ORDER BY role, username""")
    data = c.fetchall()
    
    if data:
        df = pd.DataFrame(data, columns=['ID', 'Email', 'Username', 'Role', 'Verified', 'Nama Lengkap', 'No. Telepon'])
        df['Verified'] = df['Verified'].apply(lambda x: "✅" if x == 1 else "❌")
        
        st.dataframe(df.drop('ID', axis=1), use_container_width=True)
        
        st.markdown("---")
        st.subheader("Detail User")
        
        user_id = st.selectbox("Pilih User", df['ID'].tolist(), 
                              format_func=lambda x: df[df['ID']==x]['Username'].values[0])
        
        if user_id:
            user_detail = df[df['ID']==user_id].iloc[0]
            
            col1, col2 = st.columns(2)
            col1.write(f"**Email:** {user_detail['Email']}")
            col1.write(f"**Username:** {user_detail['Username']}")
            col1.write(f"**Role:** {user_detail['Role']}")
            
            col2.write(f"**Verified:** {user_detail['Verified']}")
            col2.write(f"**Nama:** {user_detail['Nama Lengkap'] or '-'}")
            col2.write(f"**Telepon:** {user_detail['No. Telepon'] or '-'}")
            
            # Statistik user
            if user_detail['Role'] == 'kasir':
                c.execute("""SELECT COUNT(*), SUM(total) 
                             FROM transaksi_penjualan 
                             WHERE kasir_id=?""", (user_id,))
                stats = c.fetchone()
                st.info(f"📊 Total Transaksi: {stats[0]} | Total Penjualan: Rp {stats[1] or 0:,.0f}")
            
            elif user_detail['Role'] == 'karyawan':
                c.execute("""SELECT COUNT(*), SUM(total) 
                             FROM pembelian_karyawan 
                             WHERE karyawan_id=?""", (user_id,))
                stats = c.fetchone()
                st.info(f"📊 Total Pembelian: {stats[0]} | Total Nilai: Rp {stats[1] or 0:,.0f}")
    else:
        st.info("Belum ada user terdaftar")

def owner_database():
    st.subheader("🗄️ Database Management")
    
    st.warning("⚠️ Area ini untuk melihat struktur database. Hati-hati saat melakukan perubahan!")
    
    c = conn.cursor()
    
    # Daftar tabel
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = c.fetchall()
    
    if tables:
        table_name = st.selectbox("Pilih Tabel", [t[0] for t in tables])
        
        # Tampilkan data tabel
        st.markdown(f"### Data dari tabel: {table_name}")
        
        c.execute(f"SELECT * FROM {table_name}")
        data = c.fetchall()
        
        if data:
            # Get column names
            c.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in c.fetchall()]
            
            df = pd.DataFrame(data, columns=columns)
            st.dataframe(df, use_container_width=True)
            
            st.info(f"Total Records: {len(data)}")
            
            # Export ke CSV
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f"{table_name}.csv",
                mime="text/csv",
            )
        else:
            st.info("Tabel kosong")
    
    st.markdown("---")
    
    # Database Stats
    st.subheader("📊 Statistik Database")
    
    col1, col2, col3 = st.columns(3)
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    col1.metric("Total Users", total_users)
    
    c.execute("SELECT COUNT(*) FROM transaksi_penjualan")
    total_trans = c.fetchone()[0]
    col2.metric("Total Transaksi", total_trans)
    
    c.execute("SELECT COUNT(*) FROM chart_of_accounts")
    total_akun = c.fetchone()[0]
    col3.metric("Total Akun", total_akun)

# Main routing
def main():
    # ✅ Perbaiki cara baca query params
    query_params = st.query_params
    
    # Cek verifikasi email dari link
    if query_params.get('page') == 'verify':
        st.session_state.page = 'verify_email'
    elif query_params.get('page') == 'reset_password':
        st.session_state.page = 'reset_password'
    
    # Cek token untuk reset password dari Supabase
    if query_params.get('type') == 'recovery' and query_params.get('access_token'):
        st.session_state.page = 'reset_password'
        st.session_state.access_token = query_params['access_token']
    
    # Routing berdasarkan state
    if not st.session_state.logged_in:
        page = st.session_state.page
        
        if page == 'home':
            home_page()
        elif page == 'register':
            register_page()
        elif page == 'login':
            login_page()
        elif page == 'forgot_password':
            forgot_password_page()
        elif page == 'reset_password':
            reset_password_page()
        elif page == 'verify_email':
            verify_email_page()
        else:
            home_page()  # Default ke home jika tidak ada page
    else:
        # Dashboard berdasarkan role
        role = st.session_state.role
        
        if role == 'kasir':
            kasir_dashboard()
        elif role == 'akuntan':
            akuntan_dashboard()
        elif role == 'karyawan':
            karyawan_dashboard()
        elif role == 'owner':
            owner_dashboard()
        else:
            st.error("Role tidak dikenali")

if __name__ == "__main__":
    main()

# Dashboard Kasir
def kasir_dashboard():
    st.title("💰 Dashboard Kasir")
    
    with st.sidebar:
        st.markdown(f"### Halo, {st.session_state.username}!")
        st.markdown("**Role:** Kasir")
        
        menu = st.radio("Menu", ["Transaksi Penjualan", "Riwayat Transaksi", "Pengaturan Akun"])
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if menu == "Transaksi Penjualan":
        kasir_transaksi()
    elif menu == "Riwayat Transaksi":
        kasir_riwayat()
    elif menu == "Pengaturan Akun":
        pengaturan_akun()

def kasir_transaksi():
    st.subheader("🛒 Transaksi Penjualan")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### Keranjang Belanja")
        
        if 'cart' not in st.session_state:
            st.session_state.cart = []
        
        harga_per_kg = st.number_input("Harga per Kg (Rp)", min_value=0.0, value=50000.0, step=1000.0)
        jumlah_kg = st.number_input("Jumlah (Kg)", min_value=0.0, value=1.0, step=0.5)
        
        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("➕ Tambah ke Keranjang", use_container_width=True):
                if jumlah_kg > 0:
                    st.session_state.cart.append({
                        'jumlah_kg': jumlah_kg,
                        'harga_per_kg': harga_per_kg,
                        'total': jumlah_kg * harga_per_kg
                    })
                    st.success(f"Ditambahkan: {jumlah_kg} kg")
                    st.rerun()
        
        with col_clear:
            if st.button("🗑️ Kosongkan Keranjang", use_container_width=True):
                st.session_state.cart = []
                st.rerun()
        
        if st.session_state.cart:
            st.markdown("---")
            for idx, item in enumerate(st.session_state.cart):
                col_item, col_del = st.columns([4, 1])
                with col_item:
                    st.write(f"**Item {idx+1}:** {item['jumlah_kg']} kg × Rp {item['harga_per_kg']:,.0f} = Rp {item['total']:,.0f}")
                with col_del:
                    if st.button("❌", key=f"del_{idx}"):
                        st.session_state.cart.pop(idx)
                        st.rerun()
    
    with col2:
        st.markdown("### Total Belanja")
        
        if st.session_state.cart:
            total_kg = sum(item['jumlah_kg'] for item in st.session_state.cart)
            total_harga = sum(item['total'] for item in st.session_state.cart)
            
            st.metric("Total Kg", f"{total_kg} kg")
            st.metric("Total Harga", f"Rp {total_harga:,.0f}")
            
            metode_bayar = st.selectbox("Metode Pembayaran", 
                                       ["Tunai", "Kartu Debit", "Kartu Kredit", "QRIS"])
            
            if st.button("💳 Proses Pembayaran", type="primary", use_container_width=True):
                # Generate nomor struk
                now = datetime.now()
                no_struk = f"TRP{now.strftime('%Y%m%d%H%M%S')}"
                
                # Simpan transaksi
                c = conn.cursor()
                c.execute("""INSERT INTO transaksi_penjualan 
                            (no_struk, tanggal, waktu, jumlah_kg, harga_per_kg, total, metode_bayar, kasir_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                         (no_struk, now.date(), now.strftime('%H:%M:%S'), total_kg, 
                          total_harga/total_kg, total_harga, metode_bayar, st.session_state.user_id))
                conn.commit()
                
                # Auto posting ke jurnal penjualan
                c.execute("""INSERT INTO jurnal_penjualan 
                            (tanggal, no_faktur, keterangan, debit_kas, kredit_penjualan, debit_hpp, kredit_persediaan)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (now.date(), no_struk, f"Penjualan ikan mujair {total_kg} kg", 
                          total_harga, total_harga, total_harga * 0.6, total_harga * 0.6))
                conn.commit()
                
                # Cetak struk
                st.success("✅ Pembayaran Berhasil!")
                st.markdown("---")
                st.markdown(f"""
                ### 🧾 STRUK PEMBAYARAN
                
                **TILAPIA SUITE**  
                Budidaya Ikan Mujair  
                Jl. Perikanan No. 123  
                Telp: (024) 1234567
                
                ---
                
                No. Struk: **{no_struk}**  
                Tanggal: {now.strftime('%d/%m/%Y')}  
                Waktu: {now.strftime('%H:%M:%S')}  
                Kasir: {st.session_state.username}
                
                ---
                
                **DETAIL PEMBELIAN**
                
                Ikan Mujair  
                {total_kg} kg × Rp {total_harga/total_kg:,.0f} = **Rp {total_harga:,.0f}**
                
                ---
                
                **TOTAL: Rp {total_harga:,.0f}**  
                Metode Bayar: {metode_bayar}
                
                ---
                
                Terima kasih atas kunjungan Anda!  
                Selamat menikmati ikan mujair segar! 🐟
                """)
                
                # Reset keranjang
                st.session_state.cart = []
                
        else:
            st.info("Keranjang kosong")

def kasir_riwayat():
    st.subheader("📜 Riwayat Transaksi")
    
    c = conn.cursor()
    c.execute("""SELECT no_struk, tanggal, waktu, jumlah_kg, total, metode_bayar 
                 FROM transaksi_penjualan 
                 WHERE kasir_id=? 
                 ORDER BY tanggal DESC, waktu DESC""", (st.session_state.user_id,))
    
    transaksi = c.fetchall()
    
    if transaksi:
        df = pd.DataFrame(transaksi, 
                         columns=['No. Struk', 'Tanggal', 'Waktu', 'Jumlah (kg)', 'Total (Rp)', 'Metode Bayar'])
        df['Total (Rp)'] = df['Total (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        st.dataframe(df, use_container_width=True)
        
        # Grafik penjualan
        st.markdown("---")
        st.subheader("📊 Grafik Penjualan Hari Ini")
        
        df_chart = pd.DataFrame(transaksi, columns=['No. Struk', 'Tanggal', 'Waktu', 'Jumlah (kg)', 'Total (Rp)', 'Metode Bayar'])
        today = datetime.now().date()
        df_today = df_chart[df_chart['Tanggal'] == str(today)]
        
        if not df_today.empty:
            fig = px.bar(df_today, x='Waktu', y='Total (Rp)', 
                        title='Penjualan per Waktu',
                        labels={'Total (Rp)': 'Total (Rp)', 'Waktu': 'Waktu'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada transaksi hari ini")
    else:
        st.info("Belum ada riwayat transaksi")

def pengaturan_akun():
    st.subheader("⚙️ Pengaturan Akun")
    
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id=?", (st.session_state.user_id,))
    user = c.fetchone()
    
    with st.form("update_profile"):
        st.markdown("### Informasi Profil")
        nama_lengkap = st.text_input("Nama Lengkap", value=user[8] if user[8] else "")
        no_telepon = st.text_input("No. Telepon", value=user[9] if user[9] else "")
        alamat = st.text_area("Alamat", value=user[10] if user[10] else "")
        
        submit = st.form_submit_button("💾 Simpan", type="primary")
        
        if submit:
            c.execute("""UPDATE users SET nama_lengkap=?, no_telepon=?, alamat=? WHERE id=?""",
                     (nama_lengkap, no_telepon, alamat, st.session_state.user_id))
            conn.commit()
            st.success("Profil berhasil diperbarui!")
    
    st.markdown("---")
    
    with st.form("change_password"):
        st.markdown("### Ubah Password")
        old_password = st.text_input("Password Lama", type="password")
        new_password = st.text_input("Password Baru", type="password")
        confirm_new = st.text_input("Konfirmasi Password Baru", type="password")
        
        submit_pw = st.form_submit_button("🔐 Ubah Password", type="primary")
        
        if submit_pw:
            hashed_old = hash_password(old_password)
            if hashed_old != user[3]:
                st.error("Password lama salah!")
            elif new_password != confirm_new:
                st.error("Password baru tidak cocok!")
            else:
                valid, message = validate_password(new_password)
                if not valid:
                    st.error(message)
                else:
                    hashed_new = hash_password(new_password)
                    c.execute("UPDATE users SET password=? WHERE id=?", (hashed_new, st.session_state.user_id))
                    conn.commit()
                    st.success("Password berhasil diubah!")

# Dashboard Akuntan
def akuntan_dashboard():
    st.title("📊 Dashboard Akuntan")
    
    with st.sidebar:
        st.markdown(f"### Halo, {st.session_state.username}!")
        st.markdown("**Role:** Akuntan")
        
        menu = st.selectbox("Menu Utama", [
            "Dashboard",
            "Chart of Accounts",
            "Neraca Saldo Awal",
            "Jurnal Khusus",
            "Jurnal Umum",
            "Buku Besar",
            "Buku Besar Pembantu",
            "Persediaan",
            "Aset & Penyusutan",
            "Biaya",
            "Transaksi Tambahan",
            "Jurnal Penyesuaian",
            "Neraca Saldo",
            "Jurnal Penutup",
            "Jurnal Pembalik",
            "Laporan Keuangan",
            "Pengaturan Akun"
        ])
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    if menu == "Dashboard":
        akuntan_dashboard_main()
    elif menu == "Chart of Accounts":
        chart_of_accounts()
    elif menu == "Neraca Saldo Awal":
        neraca_saldo_awal()
    elif menu == "Jurnal Khusus":
        jurnal_khusus()
    elif menu == "Jurnal Umum":
        jurnal_umum()
    elif menu == "Buku Besar":
        buku_besar()
    elif menu == "Buku Besar Pembantu":
        buku_besar_pembantu()
    elif menu == "Persediaan":
        persediaan_management()
    elif menu == "Aset & Penyusutan":
        aset_management()
    elif menu == "Biaya":
        biaya_management()
    elif menu == "Transaksi Tambahan":
        transaksi_tambahan()
    elif menu == "Jurnal Penyesuaian":
        jurnal_penyesuaian()
    elif menu == "Neraca Saldo":
        neraca_saldo()
    elif menu == "Jurnal Penutup":
        jurnal_penutup()
    elif menu == "Jurnal Pembalik":
        jurnal_pembalik()
    elif menu == "Laporan Keuangan":
        laporan_keuangan()
    elif menu == "Pengaturan Akun":
        pengaturan_akun()

def akuntan_dashboard_main():
    st.subheader("📈 Ringkasan Keuangan")
    
    c = conn.cursor()
    
    # Statistik ringkas
    col1, col2, col3, col4 = st.columns(4)
    
    # Total Penjualan
    c.execute("SELECT SUM(total) FROM transaksi_penjualan")
    total_penjualan = c.fetchone()[0] or 0
    col1.metric("Total Penjualan", f"Rp {total_penjualan:,.0f}")
    
    # Total Biaya
    c.execute("SELECT SUM(nominal) FROM biaya")
    total_biaya = c.fetchone()[0] or 0
    col2.metric("Total Biaya", f"Rp {total_biaya:,.0f}")
    
    # Laba Kotor
    laba_kotor = total_penjualan - (total_penjualan * 0.6)  # Asumsi HPP 60%
    col3.metric("Laba Kotor", f"Rp {laba_kotor:,.0f}")
    
    # Laba Bersih
    laba_bersih = laba_kotor - total_biaya
    col4.metric("Laba Bersih", f"Rp {laba_bersih:,.0f}")
    
    st.markdown("---")
    
    # Grafik penjualan bulanan
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("📊 Penjualan Harian (30 Hari Terakhir)")
        c.execute("""SELECT tanggal, SUM(total) as total 
                     FROM transaksi_penjualan 
                     WHERE tanggal >= date('now', '-30 days')
                     GROUP BY tanggal 
                     ORDER BY tanggal""")
        data = c.fetchall()
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Total'])
            fig = px.line(df, x='Tanggal', y='Total', markers=True)
            fig.update_layout(yaxis_title="Total Penjualan (Rp)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data penjualan")
    
    with col_chart2:
        st.subheader("🥧 Metode Pembayaran")
        c.execute("""SELECT metode_bayar, COUNT(*) as jumlah 
                     FROM transaksi_penjualan 
                     GROUP BY metode_bayar""")
        data = c.fetchall()
        if data:
            df = pd.DataFrame(data, columns=['Metode', 'Jumlah'])
            fig = px.pie(df, values='Jumlah', names='Metode')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada data pembayaran")
    
    # Transaksi terbaru
    st.markdown("---")
    st.subheader("📜 Transaksi Terbaru")
    c.execute("""SELECT t.no_struk, t.tanggal, t.waktu, t.total, u.username 
                 FROM transaksi_penjualan t
                 LEFT JOIN users u ON t.kasir_id = u.id
                 ORDER BY t.tanggal DESC, t.waktu DESC 
                 LIMIT 10""")
    transaksi = c.fetchall()
    
    if transaksi:
        df = pd.DataFrame(transaksi, columns=['No. Struk', 'Tanggal', 'Waktu', 'Total (Rp)', 'Kasir'])
        df['Total (Rp)'] = df['Total (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Belum ada transaksi")

def chart_of_accounts():
    st.subheader("📋 Chart of Accounts (Daftar Akun)")
    
    tab1, tab2 = st.tabs(["Lihat Daftar Akun", "Tambah/Edit Akun"])
    
    with tab1:
        c = conn.cursor()
        c.execute("SELECT kode_akun, nama_akun, kategori, saldo_normal FROM chart_of_accounts ORDER BY kode_akun")
        akun = c.fetchall()
        
        if akun:
            df = pd.DataFrame(akun, columns=['Kode Akun', 'Nama Akun', 'Kategori', 'Saldo Normal'])
            
            # Filter
            kategori_filter = st.multiselect("Filter Kategori", 
                                            ['Aset', 'Liabilitas', 'Ekuitas', 'Pendapatan', 'Beban'],
                                            default=['Aset', 'Liabilitas', 'Ekuitas', 'Pendapatan', 'Beban'])
            
            df_filtered = df[df['Kategori'].isin(kategori_filter)]
            st.dataframe(df_filtered, use_container_width=True)
            
            # Tombol hapus
            st.markdown("---")
            kode_hapus = st.selectbox("Pilih akun untuk dihapus", df['Kode Akun'].tolist())
            if st.button("🗑️ Hapus Akun", type="primary"):
                c.execute("DELETE FROM chart_of_accounts WHERE kode_akun=?", (kode_hapus,))
                conn.commit()
                st.success(f"Akun {kode_hapus} berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada akun. Silakan tambah akun baru.")
    
    with tab2:
        with st.form("add_account"):
            st.markdown("### Tambah Akun Baru")
            
            kode_akun = st.text_input("Kode Akun (misal: 1-1010)")
            nama_akun = st.text_input("Nama Akun")
            kategori = st.selectbox("Kategori", ['Aset', 'Liabilitas', 'Ekuitas', 'Pendapatan', 'Beban'])
            saldo_normal = st.selectbox("Saldo Normal", ['Debit', 'Kredit'])
            
            submit = st.form_submit_button("💾 Simpan Akun", type="primary")
            
            if submit:
                if not kode_akun or not nama_akun:
                    st.error("Kode akun dan nama akun harus diisi!")
                else:
                    try:
                        c = conn.cursor()
                        c.execute("""INSERT INTO chart_of_accounts (kode_akun, nama_akun, kategori, saldo_normal)
                                    VALUES (?, ?, ?, ?)""", (kode_akun, nama_akun, kategori, saldo_normal))
                        conn.commit()
                        st.success(f"Akun {kode_akun} - {nama_akun} berhasil ditambahkan!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Kode akun sudah ada!")

def neraca_saldo_awal():
    st.subheader("📊 Neraca Saldo Awal")
    
    tab1, tab2 = st.tabs(["Lihat Neraca Saldo Awal", "Input Neraca Saldo Awal"])
    
    with tab1:
        periode = st.text_input("Periode (misal: 2024-01)", value="2024-01")
        
        c = conn.cursor()
        c.execute("""SELECT n.kode_akun, c.nama_akun, n.debit, n.kredit
                     FROM neraca_saldo_awal n
                     JOIN chart_of_accounts c ON n.kode_akun = c.kode_akun
                     WHERE n.periode = ?
                     ORDER BY n.kode_akun""", (periode,))
        
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Kode Akun', 'Nama Akun', 'Debit', 'Kredit'])
            df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            
            st.dataframe(df, use_container_width=True)
            
            # Total
            total_debit = sum([x[2] for x in data])
            total_kredit = sum([x[3] for x in data])
            
            col1, col2 = st.columns(2)
            col1.metric("Total Debit", f"Rp {total_debit:,.0f}")
            col2.metric("Total Kredit", f"Rp {total_kredit:,.0f}")
            
            if total_debit == total_kredit:
                st.success("✅ Neraca Saldo Seimbang!")
            else:
                st.error(f"⚠️ Neraca Tidak Seimbang! Selisih: Rp {abs(total_debit - total_kredit):,.0f}")
        else:
            st.info(f"Belum ada data neraca saldo untuk periode {periode}")
    
    with tab2:
        periode_input = st.text_input("Periode", value="2024-01", key="periode_input")
        
        c = conn.cursor()
        c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts ORDER BY kode_akun")
        akun_list = c.fetchall()
        
        if not akun_list:
            st.warning("Belum ada Chart of Accounts. Silakan tambah akun terlebih dahulu.")
        else:
            with st.form("input_neraca_saldo"):
                st.markdown("### Input Saldo Awal per Akun")
                
                akun_dipilih = st.selectbox("Pilih Akun", 
                                           [f"{x[0]} - {x[1]}" for x in akun_list])
                kode_akun = akun_dipilih.split(" - ")[0]
                
                col1, col2 = st.columns(2)
                debit = col1.number_input("Debit (Rp)", min_value=0.0, value=0.0, step=1000.0)
                kredit = col2.number_input("Kredit (Rp)", min_value=0.0, value=0.0, step=1000.0)
                
                submit = st.form_submit_button("💾 Simpan", type="primary")
                
                if submit:
                    if debit > 0 and kredit > 0:
                        st.error("Tidak boleh mengisi debit dan kredit sekaligus!")
                    elif debit == 0 and kredit == 0:
                        st.error("Minimal isi salah satu: debit atau kredit!")
                    else:
                        try:
                            c.execute("""INSERT INTO neraca_saldo_awal (periode, kode_akun, debit, kredit)
                                        VALUES (?, ?, ?, ?)""", (periode_input, kode_akun, debit, kredit))
                            conn.commit()
                            st.success(f"Saldo awal untuk akun {kode_akun} berhasil disimpan!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Akun ini sudah ada di periode ini. Gunakan fitur edit.")

def jurnal_khusus():
    st.subheader("📚 Jurnal Khusus")
    
    jenis_jurnal = st.selectbox("Pilih Jenis Jurnal Khusus", 
                               ["Jurnal Penjualan (SJ)", 
                                "Jurnal Pembelian (PJ)", 
                                "Jurnal Penerimaan Kas (CRJ)", 
                                "Jurnal Pengeluaran Kas (CPJ)",
                                "Jurnal Umum (GJ)"])
    
    if jenis_jurnal == "Jurnal Penjualan (SJ)":
        jurnal_penjualan()
    elif jenis_jurnal == "Jurnal Pembelian (PJ)":
        jurnal_pembelian()
    elif jenis_jurnal == "Jurnal Penerimaan Kas (CRJ)":
        jurnal_penerimaan_kas()
    elif jenis_jurnal == "Jurnal Pengeluaran Kas (CPJ)":
        jurnal_pengeluaran_kas()
    elif jenis_jurnal == "Jurnal Umum (GJ)":
        jurnal_umum()

def jurnal_penjualan():
    st.markdown("### 📗 Jurnal Penjualan")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal", "Rekapitulasi"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT id, tanggal, no_faktur, keterangan, debit_kas, kredit_penjualan, debit_hpp, kredit_persediaan
                     FROM jurnal_penjualan 
                     ORDER BY tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'No. Faktur', 'Keterangan', 
                                           'Kas (D)', 'Penjualan (K)', 'HPP (D)', 'Persediaan (K)'])
            
            # Format currency
            for col in ['Kas (D)', 'Penjualan (K)', 'HPP (D)', 'Persediaan (K)']:
                df[col] = df[col].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            # Edit/Hapus
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                id_hapus = st.selectbox("Pilih transaksi untuk dihapus", df['ID'].tolist())
                if st.button("🗑️ Hapus Transaksi", type="primary"):
                    c.execute("DELETE FROM jurnal_penjualan WHERE id=?", (id_hapus,))
                    conn.commit()
                    st.success("Transaksi berhasil dihapus!")
                    st.rerun()
        else:
            st.info("Belum ada transaksi penjualan. Transaksi otomatis tercatat saat kasir cetak struk.")
    
    with tab2:
        st.markdown("### 📊 Rekapitulasi Jurnal Penjualan")
        
        c = conn.cursor()
        c.execute("""SELECT 
                        SUM(debit_kas) as total_kas,
                        SUM(kredit_penjualan) as total_penjualan,
                        SUM(debit_hpp) as total_hpp,
                        SUM(kredit_persediaan) as total_persediaan
                     FROM jurnal_penjualan""")
        total = c.fetchone()
        
        if total and total[0]:
            st.markdown(f"""
            | Akun | Debit | Kredit |
            |------|-------|--------|
            | Kas | Rp {total[0]:,.0f} | - |
            | Penjualan | - | Rp {total[1]:,.0f} |
            | HPP | Rp {total[2]:,.0f} | - |
            | Persediaan | - | Rp {total[3]:,.0f} |
            | **TOTAL** | **Rp {(total[0] + total[2]):,.0f}** | **Rp {(total[1] + total[3]):,.0f}** |
            """)
        else:
            st.info("Belum ada data untuk rekapitulasi")

def jurnal_pembelian():
    st.markdown("### 📘 Jurnal Pembelian")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal", "Tambah Transaksi"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT id, tanggal, no_faktur, keterangan, debit_pembelian, kredit_kas, debit_persediaan
                     FROM jurnal_pembelian 
                     ORDER BY tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'No. Faktur', 'Keterangan', 
                                           'Pembelian (D)', 'Kas (K)', 'Persediaan (D)'])
            
            for col in ['Pembelian (D)', 'Kas (K)', 'Persediaan (D)']:
                df[col] = df[col].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            # Hapus
            st.markdown("---")
            id_hapus = st.selectbox("Pilih transaksi untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Transaksi", type="primary"):
                c.execute("DELETE FROM jurnal_pembelian WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Transaksi berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada transaksi pembelian")
    
    with tab2:
        with st.form("tambah_pembelian"):
            tanggal = st.date_input("Tanggal")
            no_faktur = st.text_input("No. Faktur")
            keterangan = st.text_area("Keterangan")
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit:
                if not no_faktur:
                    st.error("No. faktur harus diisi!")
                else:
                    c = conn.cursor()
                    c.execute("""INSERT INTO jurnal_pembelian 
                                (tanggal, no_faktur, keterangan, debit_pembelian, kredit_kas, debit_persediaan)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                             (tanggal, no_faktur, keterangan, nominal, nominal, nominal))
                    conn.commit()
                    st.success("Transaksi pembelian berhasil dicatat!")
                    st.rerun()

def jurnal_penerimaan_kas():
    st.markdown("### 📙 Jurnal Penerimaan Kas")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal", "Tambah Transaksi"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT id, tanggal, no_bukti, keterangan, debit_kas, kredit_akun, kredit_nominal
                     FROM jurnal_penerimaan_kas 
                     ORDER BY tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'No. Bukti', 'Keterangan', 
                                           'Kas (D)', 'Akun Kredit', 'Nominal (K)'])
            
            df['Kas (D)'] = df['Kas (D)'].apply(lambda x: f"Rp {x:,.0f}")
            df['Nominal (K)'] = df['Nominal (K)'].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            st.markdown("---")
            id_hapus = st.selectbox("Pilih transaksi untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Transaksi", type="primary"):
                c.execute("DELETE FROM jurnal_penerimaan_kas WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Transaksi berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada transaksi penerimaan kas")
    
    with tab2:
        with st.form("tambah_penerimaan"):
            tanggal = st.date_input("Tanggal")
            no_bukti = st.text_input("No. Bukti")
            keterangan = st.text_area("Keterangan")
            
            c = conn.cursor()
            c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts WHERE saldo_normal='Kredit'")
            akun_list = c.fetchall()
            
            if akun_list:
                akun_dipilih = st.selectbox("Akun yang Dikredit", 
                                           [f"{x[0]} - {x[1]}" for x in akun_list])
                kredit_akun = akun_dipilih.split(" - ")[0]
            else:
                st.warning("Belum ada akun dengan saldo normal kredit")
                kredit_akun = ""
            
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit and kredit_akun:
                c.execute("""INSERT INTO jurnal_penerimaan_kas 
                            (tanggal, no_bukti, keterangan, debit_kas, kredit_akun, kredit_nominal)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (tanggal, no_bukti, keterangan, nominal, kredit_akun, nominal))
                conn.commit()
                st.success("Transaksi penerimaan kas berhasil dicatat!")
                st.rerun()

def jurnal_pengeluaran_kas():
    st.markdown("### 📕 Jurnal Pengeluaran Kas")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal", "Tambah Transaksi"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT id, tanggal, no_bukti, keterangan, debit_akun, debit_nominal, kredit_kas
                     FROM jurnal_pengeluaran_kas 
                     ORDER BY tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'No. Bukti', 'Keterangan', 
                                           'Akun Debit', 'Nominal (D)', 'Kas (K)'])
            
            df['Nominal (D)'] = df['Nominal (D)'].apply(lambda x: f"Rp {x:,.0f}")
            df['Kas (K)'] = df['Kas (K)'].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            st.markdown("---")
            id_hapus = st.selectbox("Pilih transaksi untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Transaksi", type="primary"):
                c.execute("DELETE FROM jurnal_pengeluaran_kas WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Transaksi berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada transaksi pengeluaran kas")
    
    with tab2:
        with st.form("tambah_pengeluaran"):
            tanggal = st.date_input("Tanggal")
            no_bukti = st.text_input("No. Bukti")
            keterangan = st.text_area("Keterangan")
            
            c = conn.cursor()
            c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts WHERE saldo_normal='Debit'")
            akun_list = c.fetchall()
            
            if akun_list:
                akun_dipilih = st.selectbox("Akun yang Didebit", 
                                           [f"{x[0]} - {x[1]}" for x in akun_list])
                debit_akun = akun_dipilih.split(" - ")[0]
            else:
                st.warning("Belum ada akun dengan saldo normal debit")
                debit_akun = ""
            
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit and debit_akun:
                c.execute("""INSERT INTO jurnal_pengeluaran_kas 
                            (tanggal, no_bukti, keterangan, debit_akun, debit_nominal, kredit_kas)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (tanggal, no_bukti, keterangan, debit_akun, nominal, nominal))
                conn.commit()
                st.success("Transaksi pengeluaran kas berhasil dicatat!")
                st.rerun()

def jurnal_umum():
    st.markdown("### 📓 Jurnal Umum")
    
    tab1, tab2 = st.tabs(["Lihat Jurnal", "Tambah Transaksi"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT j.id, j.tanggal, j.kode_akun, c.nama_akun, j.keterangan, j.debit, j.kredit, j.ref
                     FROM jurnal_umum j
                     LEFT JOIN chart_of_accounts c ON j.kode_akun = c.kode_akun
                     ORDER BY j.tanggal DESC, j.id""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'Kode Akun', 'Nama Akun', 'Keterangan', 'Debit', 'Kredit', 'Ref'])
            
            df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            st.markdown("---")
            id_hapus = st.selectbox("Pilih transaksi untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Transaksi", type="primary"):
                c.execute("DELETE FROM jurnal_umum WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Transaksi berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada transaksi di jurnal umum")
    
    with tab2:
        with st.form("tambah_jurnal_umum"):
            tanggal = st.date_input("Tanggal")
            
            c = conn.cursor()
            c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts ORDER BY kode_akun")
            akun_list = c.fetchall()
            
            if not akun_list:
                st.warning("Belum ada Chart of Accounts")
            else:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Debit**")
                    akun_debit = st.selectbox("Akun Debit", 
                                             [f"{x[0]} - {x[1]}" for x in akun_list],
                                             key="debit")
                    kode_debit = akun_debit.split(" - ")[0]
                    nominal_debit = st.number_input("Nominal Debit", min_value=0.0, step=1000.0)
                
                with col2:
                    st.markdown("**Kredit**")
                    akun_kredit = st.selectbox("Akun Kredit", 
                                              [f"{x[0]} - {x[1]}" for x in akun_list],
                                              key="kredit")
                    kode_kredit = akun_kredit.split(" - ")[0]
                    nominal_kredit = st.number_input("Nominal Kredit", min_value=0.0, step=1000.0)
                
                keterangan = st.text_area("Keterangan")
                ref = st.text_input("Referensi")
                
                submit = st.form_submit_button("💾 Simpan", type="primary")
                
                if submit:
                    if nominal_debit != nominal_kredit:
                        st.error("Debit dan kredit harus sama!")
                    elif nominal_debit == 0:
                        st.error("Nominal harus lebih dari 0!")
                    else:
                        # Insert debit
                        c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                 (tanggal, kode_debit, keterangan, nominal_debit, 0, ref))
                        # Insert kredit
                        c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                                    VALUES (?, ?, ?, ?, ?, ?)""",
                                 (tanggal, kode_kredit, keterangan, 0, nominal_kredit, ref))
                        conn.commit()
                        st.success("Transaksi jurnal umum berhasil dicatat!")
                        st.rerun()

def buku_besar():
    st.subheader("📖 Buku Besar")
    
    c = conn.cursor()
    c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts ORDER BY kode_akun")
    akun_list = c.fetchall()
    
    if not akun_list:
        st.warning("Belum ada Chart of Accounts")
        return
    
    akun_dipilih = st.selectbox("Pilih Akun", [f"{x[0]} - {x[1]}" for x in akun_list])
    kode_akun = akun_dipilih.split(" - ")[0]
    
    # Ambil saldo awal
    periode = st.text_input("Periode", value="2024-01")
    c.execute("SELECT debit, kredit FROM neraca_saldo_awal WHERE kode_akun=? AND periode=?", 
             (kode_akun, periode))
    saldo_awal = c.fetchone()
    
    saldo_awal_debit = saldo_awal[0] if saldo_awal else 0
    saldo_awal_kredit = saldo_awal[1] if saldo_awal else 0
    saldo = saldo_awal_debit - saldo_awal_kredit
    
    st.info(f"Saldo Awal: Rp {abs(saldo):,.0f} ({'Debit' if saldo >= 0 else 'Kredit'})")
    
    # Ambil transaksi dari semua jurnal
    transaksi = []
    
    # Dari jurnal umum
    c.execute("""SELECT tanggal, keterangan, debit, kredit FROM jurnal_umum 
                 WHERE kode_akun=? ORDER BY tanggal""", (kode_akun,))
    transaksi.extend(c.fetchall())
    
    # Dari jurnal penyesuaian
    c.execute("""SELECT tanggal, keterangan, debit, kredit FROM jurnal_penyesuaian 
                 WHERE kode_akun=? ORDER BY tanggal""", (kode_akun,))
    transaksi.extend(c.fetchall())
    
    # Khusus untuk akun kas - dari jurnal khusus
    if "kas" in akun_dipilih.lower() or "1-1010" in kode_akun:
        c.execute("SELECT tanggal, keterangan, debit_kas, 0 FROM jurnal_penjualan ORDER BY tanggal")
        transaksi.extend(c.fetchall())
        
        c.execute("SELECT tanggal, keterangan, 0, kredit_kas FROM jurnal_pembelian ORDER BY tanggal")
        transaksi.extend(c.fetchall())
        
        c.execute("SELECT tanggal, keterangan, debit_kas, 0 FROM jurnal_penerimaan_kas ORDER BY tanggal")
        transaksi.extend(c.fetchall())
        
        c.execute("SELECT tanggal, keterangan, 0, kredit_kas FROM jurnal_pengeluaran_kas ORDER BY tanggal")
        transaksi.extend(c.fetchall())
    
    # Sort by date
    transaksi.sort(key=lambda x: x[0])
    
    if transaksi:
        # Buat tabel buku besar
        data_buku_besar = []
        
        for t in transaksi:
            saldo += t[2] - t[3]  # debit - kredit
            data_buku_besar.append({
                'Tanggal': t[0],
                'Keterangan': t[1],
                'Debit': t[2],
                'Kredit': t[3],
                'Saldo': abs(saldo),
                'D/K': 'D' if saldo >= 0 else 'K'
            })
        
        df = pd.DataFrame(data_buku_besar)
        df['Debit'] = df['Debit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
        df['Kredit'] = df['Kredit'].apply(lambda x: f"Rp {x:,.0f}" if x > 0 else "-")
        df['Saldo'] = df.apply(lambda row: f"Rp {row['Saldo']:,.0f} ({row['D/K']})", axis=1)
        
        st.dataframe(df.drop('D/K', axis=1), use_container_width=True)
        
        st.markdown("---")
        st.metric("Saldo Akhir", f"Rp {abs(saldo):,.0f} ({'Debit' if saldo >= 0 else 'Kredit'})")
    else:
        st.info("Belum ada transaksi untuk akun ini")

def buku_besar_pembantu():
    st.subheader("📋 Buku Besar Pembantu")
    
    jenis = st.selectbox("Pilih Jenis", ["Buku Besar Pembantu Piutang", "Buku Besar Pembantu Utang"])
    
    st.info("Fitur ini akan menampilkan detail piutang/utang per pelanggan/supplier")
    
    # Placeholder untuk implementasi
    st.markdown("""
    ### Coming Soon
    Fitur buku besar pembantu piutang dan utang akan segera ditambahkan.
    
    **Buku Besar Pembantu Piutang:**
    - Detail piutang per pelanggan
    - Tracking pembayaran
    
    **Buku Besar Pembantu Utang:**
    - Detail utang per supplier
    - Tracking pelunasan
    """)

def persediaan_management():
    st.subheader("📦 Manajemen Persediaan")
    
    metode = st.selectbox("Metode Penilaian Persediaan", ["FIFO", "Average"])
    
    tab1, tab2, tab3 = st.tabs(["Kartu Persediaan", "Input Transaksi", "Laporan"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT tanggal, jenis_transaksi, jumlah, harga_satuan, total, saldo_jumlah, saldo_nilai
                     FROM persediaan ORDER BY tanggal, id""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['Tanggal', 'Jenis', 'Jumlah', 'Harga/Unit', 'Total', 'Saldo Qty', 'Saldo Nilai'])
            
            for col in ['Harga/Unit', 'Total', 'Saldo Nilai']:
                df[col] = df[col].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df, use_container_width=True)
            
            # Saldo akhir
            saldo_akhir = data[-1]
            col1, col2 = st.columns(2)
            col1.metric("Saldo Kuantitas", f"{saldo_akhir[5]:,.2f} unit")
            col2.metric("Saldo Nilai", f"Rp {saldo_akhir[6]:,.0f}")
        else:
            st.info("Belum ada transaksi persediaan")
    
    with tab2:
        with st.form("input_persediaan"):
            tanggal = st.date_input("Tanggal")
            jenis = st.selectbox("Jenis Transaksi", ["Pembelian", "Penjualan", "Retur Pembelian", "Retur Penjualan"])
            jumlah = st.number_input("Jumlah", min_value=0.0, step=1.0)
            harga_satuan = st.number_input("Harga Satuan", min_value=0.0, step=1000.0)
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit:
                total = jumlah * harga_satuan
                
                # Hitung saldo
                c = conn.cursor()
                c.execute("SELECT saldo_jumlah, saldo_nilai FROM persediaan ORDER BY id DESC LIMIT 1")
                last_saldo = c.fetchone()
                
                if last_saldo:
                    saldo_qty = last_saldo[0]
                    saldo_nilai = last_saldo[1]
                else:
                    saldo_qty = 0
                    saldo_nilai = 0
                
                if jenis == "Pembelian":
                    saldo_qty += jumlah
                    saldo_nilai += total
                elif jenis == "Penjualan":
                    if metode == "FIFO":
                        # Implementasi FIFO sederhana
                        saldo_qty -= jumlah
                        saldo_nilai -= total
                    else:  # Average
                        avg_cost = saldo_nilai / saldo_qty if saldo_qty > 0 else 0
                        saldo_qty -= jumlah
                        saldo_nilai -= (jumlah * avg_cost)
                
                c.execute("""INSERT INTO persediaan 
                            (tanggal, jenis_transaksi, jumlah, harga_satuan, total, saldo_jumlah, saldo_nilai)
                            VALUES (?, ?, ?, ?, ?, ?, ?)""",
                         (tanggal, jenis, jumlah, harga_satuan, total, saldo_qty, saldo_nilai))
                conn.commit()
                st.success("Transaksi persediaan berhasil dicatat!")
                st.rerun()
    
    with tab3:
        st.markdown("### 📊 Laporan Persediaan")
        
        c = conn.cursor()
        c.execute("""SELECT 
                        SUM(CASE WHEN jenis_transaksi='Pembelian' THEN jumlah ELSE 0 END) as total_pembelian,
                        SUM(CASE WHEN jenis_transaksi='Penjualan' THEN jumlah ELSE 0 END) as total_penjualan,
                        (SELECT saldo_jumlah FROM persediaan ORDER BY id DESC LIMIT 1) as saldo_akhir
                     FROM persediaan""")
        data = c.fetchone()
        
        if data and data[0]:
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Pembelian", f"{data[0]:,.2f} unit")
            col2.metric("Total Penjualan", f"{data[1]:,.2f} unit")
            col3.metric("Saldo Akhir", f"{data[2]:,.2f} unit")
        else:
            st.info("Belum ada data persediaan")

def aset_management():
    st.subheader("🏢 Manajemen Aset & Penyusutan")
    
    tab1, tab2, tab3 = st.tabs(["Daftar Aset", "Tambah Aset", "Hitung Penyusutan"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT id, nama_aset, tanggal_perolehan, harga_perolehan, metode_penyusutan, 
                            akumulasi_penyusutan, (harga_perolehan - akumulasi_penyusutan) as nilai_buku
                     FROM aset ORDER BY tanggal_perolehan DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Nama Aset', 'Tgl Perolehan', 'Harga Perolehan', 
                                           'Metode', 'Akum. Penyusutan', 'Nilai Buku'])
            
            for col in ['Harga Perolehan', 'Akum. Penyusutan', 'Nilai Buku']:
                df[col] = df[col].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            st.markdown("---")
            id_hapus = st.selectbox("Pilih aset untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Aset", type="primary"):
                c.execute("DELETE FROM aset WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Aset berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada aset terdaftar")
    
    with tab2:
        with st.form("tambah_aset"):
            nama_aset = st.text_input("Nama Aset")
            tanggal_perolehan = st.date_input("Tanggal Perolehan")
            harga_perolehan = st.number_input("Harga Perolehan (Rp)", min_value=0.0, step=1000.0)
            nilai_residu = st.number_input("Nilai Residu (Rp)", min_value=0.0, step=1000.0)
            umur_ekonomis = st.number_input("Umur Ekonomis (tahun)", min_value=1, step=1)
            metode = st.selectbox("Metode Penyusutan", 
                                 ["Garis Lurus", "Saldo Menurun", "Jumlah Angka Tahun"])
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit:
                if not nama_aset:
                    st.error("Nama aset harus diisi!")
                else:
                    c = conn.cursor()
                    c.execute("""INSERT INTO aset 
                                (nama_aset, tanggal_perolehan, harga_perolehan, nilai_residu, 
                                 umur_ekonomis, metode_penyusutan, akumulasi_penyusutan)
                                VALUES (?, ?, ?, ?, ?, ?, 0)""",
                             (nama_aset, tanggal_perolehan, harga_perolehan, nilai_residu, 
                              umur_ekonomis, metode))
                    conn.commit()
                    st.success(f"Aset {nama_aset} berhasil ditambahkan!")
                    st.rerun()
    
    with tab3:
        st.markdown("### 🧮 Perhitungan Penyusutan")
        
        c = conn.cursor()
        c.execute("SELECT id, nama_aset FROM aset")
        aset_list = c.fetchall()
        
        if not aset_list:
            st.warning("Belum ada aset untuk dihitung penyusutannya")
        else:
            aset_dipilih = st.selectbox("Pilih Aset", [f"{x[0]} - {x[1]}" for x in aset_list])
            id_aset = int(aset_dipilih.split(" - ")[0])
            
            c.execute("""SELECT harga_perolehan, nilai_residu, umur_ekonomis, metode_penyusutan, akumulasi_penyusutan
                         FROM aset WHERE id=?""", (id_aset,))
            aset = c.fetchone()
            
            harga = aset[0]
            residu = aset[1]
            umur = aset[2]
            metode = aset[3]
            akum = aset[4]
            
            if metode == "Garis Lurus":
                penyusutan_per_tahun = (harga - residu) / umur
                st.info(f"Penyusutan per tahun: Rp {penyusutan_per_tahun:,.0f}")
            elif metode == "Saldo Menurun":
                rate = 2 / umur
                nilai_buku = harga - akum
                penyusutan_tahun_ini = nilai_buku * rate
                st.info(f"Penyusutan tahun ini: Rp {penyusutan_tahun_ini:,.0f}")
                penyusutan_per_tahun = penyusutan_tahun_ini
            else:  # Jumlah Angka Tahun
                sum_years = sum(range(1, umur + 1))
                tahun_ke = 1  # Bisa disesuaikan
                penyusutan_per_tahun = ((umur - tahun_ke + 1) / sum_years) * (harga - residu)
                st.info(f"Penyusutan tahun ke-{tahun_ke}: Rp {penyusutan_per_tahun:,.0f}")
            
            if st.button("✅ Catat Penyusutan", type="primary"):
                new_akum = akum + penyusutan_per_tahun
                c.execute("UPDATE aset SET akumulasi_penyusutan=? WHERE id=?", (new_akum, id_aset))
                
                # Catat ke jurnal penyesuaian
                tanggal_sekarang = datetime.now().date()
                c.execute("""INSERT INTO jurnal_penyesuaian (tanggal, kode_akun, keterangan, debit, kredit)
                            VALUES (?, ?, ?, ?, ?)""",
                         (tanggal_sekarang, '5-1010', f'Penyusutan {aset_list[id_aset-1][1]}', 
                          penyusutan_per_tahun, 0))
                c.execute("""INSERT INTO jurnal_penyesuaian (tanggal, kode_akun, keterangan, debit, kredit)
                            VALUES (?, ?, ?, ?, ?)""",
                         (tanggal_sekarang, '1-1020', f'Akumulasi Penyusutan {aset_list[id_aset-1][1]}', 
                          0, penyusutan_per_tahun))
                conn.commit()
                st.success("Penyusutan berhasil dicatat!")
                st.rerun()

def biaya_management():
    st.subheader("💸 Manajemen Biaya")
    
    tab1, tab2 = st.tabs(["Daftar Biaya", "Tambah Biaya"])
    
    with tab1:
        c = conn.cursor()
        c.execute("""SELECT b.id, b.tanggal, b.kategori_biaya, b.keterangan, b.nominal, b.kode_akun, c.nama_akun
                     FROM biaya b
                     LEFT JOIN chart_of_accounts c ON b.kode_akun = c.kode_akun
                     ORDER BY b.tanggal DESC""")
        data = c.fetchall()
        
        if data:
            df = pd.DataFrame(data, columns=['ID', 'Tanggal', 'Kategori', 'Keterangan', 'Nominal', 'Kode Akun', 'Nama Akun'])
            df['Nominal'] = df['Nominal'].apply(lambda x: f"Rp {x:,.0f}")
            
            st.dataframe(df.drop('ID', axis=1), use_container_width=True)
            
            # Total biaya per kategori
            st.markdown("---")
            st.subheader("📊 Total Biaya per Kategori")
            
            c.execute("""SELECT kategori_biaya, SUM(nominal) as total
                         FROM biaya GROUP BY kategori_biaya""")
            kategori_data = c.fetchall()
            
            if kategori_data:
                df_kategori = pd.DataFrame(kategori_data, columns=['Kategori', 'Total'])
                fig = px.bar(df_kategori, x='Kategori', y='Total', 
                           title='Total Biaya per Kategori')
                st.plotly_chart(fig, use_container_width=True)
            
            # Hapus
            st.markdown("---")
            id_hapus = st.selectbox("Pilih biaya untuk dihapus", df['ID'].tolist())
            if st.button("🗑️ Hapus Biaya", type="primary"):
                c.execute("DELETE FROM biaya WHERE id=?", (id_hapus,))
                conn.commit()
                st.success("Biaya berhasil dihapus!")
                st.rerun()
        else:
            st.info("Belum ada biaya tercatat")
    
    with tab2:
        with st.form("tambah_biaya"):
            tanggal = st.date_input("Tanggal")
            
            kategori_options = [
                "Biaya Pakan",
                "Biaya Listrik",
                "Biaya Air",
                "Biaya Gaji",
                "Biaya Perawatan",
                "Biaya Transportasi",
                "Biaya Lain-lain"
            ]
            
            kategori = st.selectbox("Kategori Biaya", kategori_options)
            keterangan = st.text_area("Keterangan")
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
            
            c = conn.cursor()
            c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts WHERE kategori='Beban'")
            akun_list = c.fetchall()
            
            if akun_list:
                akun_dipilih = st.selectbox("Akun Beban", [f"{x[0]} - {x[1]}" for x in akun_list])
                kode_akun = akun_dipilih.split(" - ")[0]
            else:
                st.warning("Belum ada akun beban di Chart of Accounts")
                kode_akun = None
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit and kode_akun:
                c.execute("""INSERT INTO biaya (tanggal, kategori_biaya, keterangan, nominal, kode_akun)
                            VALUES (?, ?, ?, ?, ?)""",
                         (tanggal, kategori, keterangan, nominal, kode_akun))
                
                # Auto posting ke jurnal pengeluaran kas
                c.execute("""INSERT INTO jurnal_pengeluaran_kas 
                            (tanggal, no_bukti, keterangan, debit_akun, debit_nominal, kredit_kas)
                            VALUES (?, ?, ?, ?, ?, ?)""",
                         (tanggal, f"BYA{datetime.now().strftime('%Y%m%d%H%M%S')}", 
                          keterangan, kode_akun, nominal, nominal))
                
                conn.commit()
                st.success("Biaya berhasil dicatat!")
                st.rerun()

def transaksi_tambahan():
    st.subheader("➕ Transaksi Tambahan")
    
    st.info("Fitur ini untuk mencatat transaksi di luar penjualan dan pembelian reguler")
    
    with st.form("transaksi_tambahan"):
        tanggal = st.date_input("Tanggal")
        jenis = st.selectbox("Jenis Transaksi", 
                            ["Pembelian Peralatan", "Penerimaan Piutang", 
                             "Pembayaran Utang", "Investasi Pemilik", "Prive"])
        
        c = conn.cursor()
        c.execute("SELECT kode_akun, nama_akun FROM chart_of_accounts ORDER BY kode_akun")
        akun_list = c.fetchall()
        
        if not akun_list:
            st.warning("Belum ada Chart of Accounts")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                akun_debit = st.selectbox("Akun Debit", [f"{x[0]} - {x[1]}" for x in akun_list])
                kode_debit = akun_debit.split(" - ")[0]
            
            with col2:
                akun_kredit = st.selectbox("Akun Kredit", [f"{x[0]} - {x[1]}" for x in akun_list])
                kode_kredit = akun_kredit.split(" - ")[0]
            
            nominal = st.number_input("Nominal (Rp)", min_value=0.0, step=1000.0)
            keterangan = st.text_area("Keterangan")
            
            submit = st.form_submit_button("💾 Simpan", type="primary")
            
            if submit:
                if nominal == 0:
                    st.error("Nominal harus lebih dari 0!")
                else:
                    # Insert ke jurnal umum
                    c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                             (tanggal, kode_debit, f"{jenis} - {keterangan}", nominal, 0, jenis))
                    c.execute("""INSERT INTO jurnal_umum (tanggal, kode_akun, keterangan, debit, kredit, ref)
                                VALUES (?, ?, ?, ?, ?, ?)""",
                             (tanggal, kode_kredit, f"{jenis} - {keterangan}", 0, nominal, jenis))
                    conn.commit()
                    st.success
