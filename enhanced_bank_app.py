import mysql.connector
import random
import hashlib
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import getpass
import re
import json

class EnhancedBankApp:
    def __init__(self):
        self.db_connection = self.connect_db()
        self.current_user = None
        self.current_admin = None
        self.transaction_limit = 50000  # Daily transaction limit
        
    def connect_db(self):
        """Establish database connection with your credentials"""
        try:
            return mysql.connector.connect(
                host="localhost",
                user="root",
                password="root",  # MySQL password
                database="bank_app",
                auth_plugin='mysql_native_password'
            )
        except mysql.connector.Error as err:
            print(f"Database connection error: {err}")
            print("Please ensure MySQL is running and the 'bank_app' database exists.")
            return None

    def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.db_connection.cursor()
            
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_number VARCHAR(20) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    phone VARCHAR(15) NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    date_of_birth DATE,
                    address TEXT,
                    id_proof_type ENUM('AADHAAR', 'PAN', 'DRIVING_LICENSE', 'PASSPORT'),
                    id_proof_number VARCHAR(50),
                    account_type ENUM('SAVINGS', 'CURRENT', 'SALARY', 'FIXED_DEPOSIT') DEFAULT 'SAVINGS',
                    balance DECIMAL(15,2) DEFAULT 0.00,
                    status ENUM('ACTIVE', 'INACTIVE', 'SUSPENDED') DEFAULT 'ACTIVE',
                    last_login DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_number VARCHAR(20) NOT NULL,
                    transaction_type ENUM('DEPOSIT', 'WITHDRAWAL', 'TRANSFER') NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    recipient_account VARCHAR(20),
                    recipient_name VARCHAR(100),
                    description TEXT,
                    reference_number VARCHAR(50) UNIQUE NOT NULL,
                    balance_after DECIMAL(15,2),
                    status ENUM('SUCCESS', 'FAILED', 'PENDING') DEFAULT 'SUCCESS',
                    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_number) REFERENCES users(account_number)
                )
            """)
            
            # Create beneficiaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS beneficiaries (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_account VARCHAR(20) NOT NULL,
                    beneficiary_account VARCHAR(20) NOT NULL,
                    beneficiary_name VARCHAR(100) NOT NULL,
                    nickname VARCHAR(50),
                    bank_name VARCHAR(100),
                    ifsc_code VARCHAR(20),
                    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_account) REFERENCES users(account_number)
                )
            """)
            
            # Create fixed_deposits table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fixed_deposits (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_number VARCHAR(20) NOT NULL,
                    fd_number VARCHAR(20) UNIQUE NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    interest_rate DECIMAL(5,2) NOT NULL,
                    tenure_months INT NOT NULL,
                    start_date DATE NOT NULL,
                    maturity_date DATE NOT NULL,
                    maturity_amount DECIMAL(15,2) NOT NULL,
                    status ENUM('ACTIVE', 'MATURED', 'CLOSED') DEFAULT 'ACTIVE',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_number) REFERENCES users(account_number)
                )
            """)
            
            # Create loans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    account_number VARCHAR(20) NOT NULL,
                    loan_id VARCHAR(20) UNIQUE NOT NULL,
                    loan_type ENUM('PERSONAL', 'HOME', 'CAR', 'EDUCATION') NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    interest_rate DECIMAL(5,2) NOT NULL,
                    tenure_months INT NOT NULL,
                    emi_amount DECIMAL(15,2) NOT NULL,
                    status ENUM('PENDING', 'APPROVED', 'REJECTED', 'DISBURSED') DEFAULT 'PENDING',
                    disbursement_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_number) REFERENCES users(account_number)
                )
            """)
            
            # Create audit_log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    action VARCHAR(100) NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create otp_store table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_store (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    email VARCHAR(100) NOT NULL,
                    otp VARCHAR(10) NOT NULL,
                    purpose ENUM('LOGIN', 'TRANSACTION') DEFAULT 'LOGIN',
                    is_used BOOLEAN DEFAULT FALSE,
                    expires_at DATETIME NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.db_connection.commit()
            cursor.close()
            print("✓ Database tables created/verified successfully!")
            return True
            
        except mysql.connector.Error as err:
            print(f"Error creating tables: {err}")
            return False

    def create_admin_tables(self):
        """Create admin-related tables"""
        try:
            cursor = self.db_connection.cursor()
            
            # Create admins table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    role ENUM('SUPER_ADMIN', 'ADMIN', 'SUPPORT') DEFAULT 'ADMIN',
                    permissions JSON,
                    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
                    last_login DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create system_settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    setting_key VARCHAR(100) UNIQUE NOT NULL,
                    setting_value TEXT,
                    description TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            
            # Insert default admin if not exists
            cursor.execute("SELECT id FROM admins WHERE username = 'admin'")
            if not cursor.fetchone():
                default_password = self.hash_password("admin123")
                cursor.execute(
                    "INSERT INTO admins (username, password, email, role) VALUES (%s, %s, %s, %s)",
                    ('admin', default_password, 'admin@bank.com', 'SUPER_ADMIN')
                )
            
            # Insert default settings
            default_settings = [
                ('daily_transaction_limit', '50000', 'Maximum daily transaction limit per user'),
                ('max_login_attempts', '3', 'Maximum login attempts before lockout'),
                ('otp_validity_minutes', '10', 'OTP validity period in minutes'),
                ('maintenance_mode', 'false', 'System maintenance mode'),
                ('currency', 'INR', 'Default currency')
            ]
            
            for key, value, description in default_settings:
                cursor.execute(
                    "INSERT IGNORE INTO system_settings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
                    (key, value, description)
                )
            
            self.db_connection.commit()
            cursor.close()
            print("✓ Admin tables created successfully!")
            return True
            
        except mysql.connector.Error as err:
            print(f"Error creating admin tables: {err}")
            return False

    def log_audit(self, action, description=""):
        """Log user actions for security"""
        try:
            cursor = self.db_connection.cursor()
            user_id = self.current_user['id'] if self.current_user else None
            cursor.execute(
                "INSERT INTO audit_log (user_id, action, description) VALUES (%s, %s, %s)",
                (user_id, action, description)
            )
            self.db_connection.commit()
            cursor.close()
        except mysql.connector.Error as err:
            print(f"Audit log error: {err}")

    def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def generate_otp(self):
        """Generate 6-digit OTP"""
        return str(random.randint(100000, 999999))

    def generate_reference_number(self):
        """Generate unique transaction reference number"""
        return f"TXN{datetime.now().strftime('%Y%m%d')}{random.randint(100000, 999999)}"

    def validate_email(self, email):
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def validate_phone(self, phone):
        """Validate phone number"""
        pattern = r'^[6-9]\d{9}$'  # Indian mobile numbers
        return re.match(pattern, phone) is not None

    def validate_pan(self, pan):
        """Validate PAN card number"""
        pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
        return re.match(pattern, pan) is not None

    def send_email(self, email, subject, body):
        """Send email to user using your Gmail account"""
        try:
            # Your email configuration
            sender_email = "computerrp14@gmail.com"
            sender_password = "wydj hbze xpcx vxum"  # Your Gmail app password
            
            message = MIMEText(body, "html")
            message["Subject"] = subject
            message["From"] = sender_email
            message["To"] = email
            
            # For Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_password)
                server.send_message(message)
            
            return True
        except Exception as e:
            print(f"Error sending email: {e}")
            print("Please check your email credentials and internet connection.")
            return False

    def send_otp_email(self, email, otp, purpose="LOGIN"):
        """Send OTP email with proper formatting"""
        if purpose == "LOGIN":
            subject = "Your Login OTP - Bank App"
            body = f"""
            <html>
                <body>
                    <h2>Login OTP</h2>
                    <p>Your One-Time Password for login is: <strong>{otp}</strong></p>
                    <p>This OTP is valid for 10 minutes.</p>
                    <p>If you didn't request this, please ignore this email.</p>
                </body>
            </html>
            """
        else:
            subject = "Your Transaction OTP - Bank App"
            body = f"""
            <html>
                <body>
                    <h2>Transaction OTP</h2>
                    <p>Your One-Time Password for transaction is: <strong>{otp}</strong></p>
                    <p>This OTP is valid for 10 minutes.</p>
                    <p>If you didn't request this, please contact support immediately.</p>
                </body>
            </html>
            """
        
        return self.send_email(email, subject, body)

    def store_otp(self, email, otp, purpose="LOGIN"):
        """Store OTP in database"""
        try:
            cursor = self.db_connection.cursor()
            expires_at = datetime.now() + timedelta(minutes=10)
            
            cursor.execute(
                "INSERT INTO otp_store (email, otp, purpose, expires_at) VALUES (%s, %s, %s, %s)",
                (email, otp, purpose, expires_at)
            )
            
            self.db_connection.commit()
            cursor.close()
            return True
        except mysql.connector.Error as err:
            print(f"Error storing OTP: {err}")
            return False

    def verify_otp(self, email, otp, purpose="LOGIN"):
        """Verify OTP from database"""
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT id FROM otp_store WHERE email = %s AND otp = %s AND purpose = %s AND is_used = FALSE AND expires_at > %s",
                (email, otp, purpose, datetime.now())
            )
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                cursor = self.db_connection.cursor()
                cursor.execute("UPDATE otp_store SET is_used = TRUE WHERE id = %s", (result[0],))
                self.db_connection.commit()
                cursor.close()
                return True
            
            return False
        except mysql.connector.Error as err:
            print(f"Error verifying OTP: {err}")
            return False

    def register_user(self):
        """Enhanced user registration with KYC"""
        print("\n=== User Registration (KYC Process) ===")
        
        try:
            # Personal Information
            name = input("Enter full name: ")
            email = input("Enter email: ")
            
            if not self.validate_email(email):
                print("Invalid email format.")
                return False
            
            # Check if email already exists
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                print("Email already registered.")
                cursor.close()
                return False
            cursor.close()
            
            phone = input("Enter phone number: ")
            if not self.validate_phone(phone):
                print("Invalid phone number.")
                return False
            
            date_of_birth = input("Enter date of birth (YYYY-MM-DD): ")
            address = input("Enter address: ")
            
            # KYC Information
            print("\n=== KYC Verification ===")
            print("ID Proof Types: AADHAAR, PAN, DRIVING_LICENSE, PASSPORT")
            id_proof_type = input("Enter ID proof type: ").upper()
            id_proof_number = input("Enter ID proof number: ")
            
            if id_proof_type == "PAN" and not self.validate_pan(id_proof_number):
                print("Invalid PAN card number.")
                return False
            
            # Account Information
            print("\n=== Account Type Selection ===")
            print("1. Savings Account (4% interest)")
            print("2. Current Account (No interest)")
            print("3. Salary Account (3% interest)")
            print("4. Fixed Deposit Account (6% interest)")
            
            account_choice = input("Select account type (1-4): ")
            account_types = {
                '1': 'SAVINGS',
                '2': 'CURRENT',
                '3': 'SALARY',
                '4': 'FIXED_DEPOSIT'
            }
            
            account_type = account_types.get(account_choice, 'SAVINGS')
            initial_deposit = float(input("Enter initial deposit amount: ₹"))
            
            if initial_deposit < 0:
                print("Initial deposit cannot be negative.")
                return False
            
            password = getpass.getpass("Set your password: ")
            confirm_password = getpass.getpass("Confirm password: ")
            
            if password != confirm_password:
                print("Passwords do not match.")
                return False
            
            # Generate account number
            account_number = f"BANK{random.randint(1000000000, 9999999999)}"
            
            cursor = self.db_connection.cursor()
            cursor.execute(
                """INSERT INTO users 
                (account_number, name, email, phone, password, date_of_birth, address, 
                 id_proof_type, id_proof_number, account_type, balance) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (account_number, name, email, phone, self.hash_password(password), 
                 date_of_birth, address, id_proof_type, id_proof_number, 
                 account_type, initial_deposit)
            )
            
            # Record initial deposit transaction
            reference_number = self.generate_reference_number()
            cursor.execute(
                """INSERT INTO transactions 
                (account_number, transaction_type, amount, description, reference_number, balance_after) 
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (account_number, 'DEPOSIT', initial_deposit, 'Initial deposit', reference_number, initial_deposit)
            )
            
            self.db_connection.commit()
            cursor.close()
            
            # Send welcome email
            welcome_body = f"""
            <html>
                <body>
                    <h2>Welcome to Our Bank!</h2>
                    <p>Dear {name},</p>
                    <p>Your account has been successfully created.</p>
                    <p><strong>Account Number:</strong> {account_number}</p>
                    <p><strong>Account Type:</strong> {account_type}</p>
                    <p><strong>Initial Balance:</strong> ₹{initial_deposit:.2f}</p>
                    <p>Thank you for choosing us!</p>
                </body>
            </html>
            """
            self.send_email(email, "Welcome to Our Bank", welcome_body)
            
            print(f"\nRegistration successful!")
            print(f"Your account number is: {account_number}")
            self.log_audit("USER_REGISTRATION", f"New user registered: {account_number}")
            return True
            
        except ValueError:
            print("Invalid amount entered.")
            return False
        except mysql.connector.Error as err:
            print(f"Registration failed: {err}")
            return False

    def login_with_otp(self):
        """Enhanced login with security features"""
        print("\n=== Secure Login ===")
        
        email = input("Enter email: ")
        
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s AND status = 'ACTIVE'", (email,))
            user = cursor.fetchone()
            cursor.close()
            
            if not user:
                print("Account not found or inactive.")
                return None
            
            # Generate and send OTP
            otp = self.generate_otp()
            if self.store_otp(email, otp) and self.send_otp_email(email, otp):
                print("OTP sent to your registered email. Please check your inbox.")
                
                # Verify OTP
                entered_otp = input("Enter OTP: ")
                if self.verify_otp(email, entered_otp):
                    # Update last login
                    cursor = self.db_connection.cursor()
                    cursor.execute("UPDATE users SET last_login = %s WHERE email = %s", (datetime.now(), email))
                    self.db_connection.commit()
                    cursor.close()
                    
                    print("Login successful!")
                    self.current_user = user
                    self.log_audit("USER_LOGIN", "User logged in successfully")
                    return user
                else:
                    print("Invalid or expired OTP.")
                    self.log_audit("LOGIN_FAILED", "Invalid OTP entered")
                    return None
            else:
                print("Failed to send OTP. Please try again.")
                return None
                
        except mysql.connector.Error as err:
            print(f"Login error: {err}")
            return None

    def admin_login(self):
        """Admin login"""
        print("\n=== Admin Login ===")
        
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM admins WHERE username = %s AND status = 'ACTIVE'",
                (username,)
            )
            admin = cursor.fetchone()
            cursor.close()
            
            if admin and self.hash_password(password) == admin['password']:
                # Update last login
                cursor = self.db_connection.cursor()
                cursor.execute(
                    "UPDATE admins SET last_login = %s WHERE id = %s",
                    (datetime.now(), admin['id'])
                )
                self.db_connection.commit()
                cursor.close()
                
                print("✓ Admin login successful!")
                self.current_admin = admin
                return True
            else:
                print("✗ Invalid credentials or inactive account.")
                return False
                
        except mysql.connector.Error as err:
            print(f"Login error: {err}")
            return False

    def check_daily_limit(self, amount):
        """Check if transaction exceeds daily limit"""
        try:
            cursor = self.db_connection.cursor()
            today = datetime.now().date()
            cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) FROM transactions 
                WHERE account_number = %s AND transaction_type IN ('WITHDRAWAL', 'TRANSFER') 
                AND DATE(transaction_date) = %s AND status = 'SUCCESS'""",
                (self.current_user['account_number'], today)
            )
            daily_total = cursor.fetchone()[0]
            cursor.close()
            
            return (daily_total + amount) <= self.transaction_limit
        except mysql.connector.Error as err:
            print(f"Error checking daily limit: {err}")
            return False

    def check_balance(self):
        """Check account balance with details"""
        print(f"\n=== Account Summary ===")
        print(f"Account Holder: {self.current_user['name']}")
        print(f"Account Number: {self.current_user['account_number']}")
        print(f"Account Type: {self.current_user['account_type']}")
        print(f"Available Balance: ₹{self.current_user['balance']:.2f}")
        
        # Show recent transactions
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM transactions WHERE account_number = %s ORDER BY transaction_date DESC LIMIT 5",
                (self.current_user['account_number'],)
            )
            recent_transactions = cursor.fetchall()
            cursor.close()
            
            if recent_transactions:
                print("\nRecent Transactions:")
                for transaction in recent_transactions:
                    print(f"  {transaction['transaction_date']} - {transaction['transaction_type']} - ₹{transaction['amount']:.2f}")
        
        except mysql.connector.Error as err:
            print(f"Error fetching recent transactions: {err}")

    def deposit(self):
        """Deposit money with transaction OTP"""
        try:
            amount = float(input("Enter amount to deposit: ₹"))
            if amount <= 0:
                print("Amount must be positive.")
                return
            
            # Generate transaction OTP
            otp = self.generate_otp()
            if self.store_otp(self.current_user['email'], otp, "TRANSACTION") and \
               self.send_otp_email(self.current_user['email'], otp, "TRANSACTION"):
                print("Transaction OTP sent to your email.")
                
                entered_otp = input("Enter transaction OTP: ")
                if self.verify_otp(self.current_user['email'], entered_otp, "TRANSACTION"):
                    cursor = self.db_connection.cursor()
                    
                    # Update balance
                    new_balance = self.current_user['balance'] + amount
                    cursor.execute(
                        "UPDATE users SET balance = %s WHERE account_number = %s",
                        (new_balance, self.current_user['account_number'])
                    )
                    
                    # Record transaction
                    reference_number = self.generate_reference_number()
                    cursor.execute(
                        """INSERT INTO transactions 
                        (account_number, transaction_type, amount, description, reference_number, balance_after) 
                        VALUES (%s, %s, %s, %s, %s, %s)""",
                        (self.current_user['account_number'], 'DEPOSIT', amount, 
                         'Cash deposit', reference_number, new_balance)
                    )
                    
                    self.db_connection.commit()
                    cursor.close()
                    
                    # Update current user balance
                    self.current_user['balance'] = new_balance
                    
                    print(f"Successfully deposited ₹{amount:.2f}")
                    print(f"Reference Number: {reference_number}")
                    self.log_audit("DEPOSIT", f"Amount: ₹{amount:.2f}, Ref: {reference_number}")
                    
                    # Send transaction alert
                    alert_body = f"""
                    <html>
                        <body>
                            <h3>Transaction Alert</h3>
                            <p>Dear {self.current_user['name']},</p>
                            <p>Your account has been credited with ₹{amount:.2f}</p>
                            <p><strong>Reference Number:</strong> {reference_number}</p>
                            <p><strong>Available Balance:</strong> ₹{new_balance:.2f}</p>
                        </body>
                    </html>
                    """
                    self.send_email(self.current_user['email'], "Transaction Alert - Deposit", alert_body)
                else:
                    print("Invalid transaction OTP.")
            else:
                print("Failed to send transaction OTP.")
            
        except ValueError:
            print("Invalid amount.")
        except mysql.connector.Error as err:
            print(f"Deposit failed: {err}")

    def withdraw(self):
        """Withdraw money with security checks"""
        try:
            amount = float(input("Enter amount to withdraw: ₹"))
            if amount <= 0:
                print("Amount must be positive.")
                return
            
            # Check sufficient balance
            if self.current_user['balance'] < amount:
                print("Insufficient balance.")
                return
            
            # Check daily limit
            if not self.check_daily_limit(amount):
                print(f"Transaction exceeds daily limit of ₹{self.transaction_limit:.2f}")
                return
            
            # Generate transaction OTP
            otp = self.generate_otp()
            if self.store_otp(self.current_user['email'], otp, "TRANSACTION") and \
               self.send_otp_email(self.current_user['email'], otp, "TRANSACTION"):
                print("Transaction OTP sent to your email.")
                
                entered_otp = input("Enter transaction OTP: ")
                if self.verify_otp(self.current_user['email'], entered_otp, "TRANSACTION"):
                    cursor = self.db_connection.cursor()
                    
                    # Update balance
                    new_balance = self.current_user['balance'] - amount
                    cursor.execute(
                        "UPDATE users SET balance = %s WHERE account_number = %s",
                        (new_balance, self.current_user['account_number'])
                    )
                    
                    # Record transaction
                    reference_number = self.generate_reference_number()
                    cursor.execute(
                        """INSERT INTO transactions 
                        (account_number, transaction_type, amount, description, reference_number, balance_after) 
                        VALUES (%s, %s, %s, %s, %s, %s)""",
                        (self.current_user['account_number'], 'WITHDRAWAL', amount, 
                         'Cash withdrawal', reference_number, new_balance)
                    )
                    
                    self.db_connection.commit()
                    cursor.close()
                    
                    # Update current user balance
                    self.current_user['balance'] = new_balance
                    
                    print(f"Successfully withdrew ₹{amount:.2f}")
                    print(f"Reference Number: {reference_number}")
                    self.log_audit("WITHDRAWAL", f"Amount: ₹{amount:.2f}, Ref: {reference_number}")
                    
                    # Send transaction alert
                    alert_body = f"""
                    <html>
                        <body>
                            <h3>Transaction Alert</h3>
                            <p>Dear {self.current_user['name']},</p>
                            <p>Your account has been debited with ₹{amount:.2f}</p>
                            <p><strong>Reference Number:</strong> {reference_number}</p>
                            <p><strong>Available Balance:</strong> ₹{new_balance:.2f}</p>
                        </body>
                    </html>
                    """
                    self.send_email(self.current_user['email'], "Transaction Alert - Withdrawal", alert_body)
                else:
                    print("Invalid transaction OTP.")
            else:
                print("Failed to send transaction OTP.")
            
        except ValueError:
            print("Invalid amount.")
        except mysql.connector.Error as err:
            print(f"Withdrawal failed: {err}")

    def add_beneficiary(self):
        """Add beneficiary for quick transfers"""
        print("\n=== Add Beneficiary ===")
        
        beneficiary_account = input("Enter beneficiary account number: ")
        beneficiary_name = input("Enter beneficiary name: ")
        nickname = input("Enter nickname (optional): ")
        bank_name = input("Enter bank name: ")
        ifsc_code = input("Enter IFSC code: ")
        
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                """INSERT INTO beneficiaries 
                (user_account, beneficiary_account, beneficiary_name, nickname, bank_name, ifsc_code) 
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (self.current_user['account_number'], beneficiary_account, beneficiary_name, 
                 nickname, bank_name, ifsc_code)
            )
            
            self.db_connection.commit()
            cursor.close()
            
            print("Beneficiary added successfully!")
            self.log_audit("ADD_BENEFICIARY", f"Added beneficiary: {beneficiary_name}")
            
        except mysql.connector.Error as err:
            print(f"Failed to add beneficiary: {err}")

    def view_beneficiaries(self):
        """View all beneficiaries"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM beneficiaries WHERE user_account = %s AND status = 'ACTIVE'",
                (self.current_user['account_number'],)
            )
            
            beneficiaries = cursor.fetchall()
            cursor.close()
            
            if not beneficiaries:
                print("No beneficiaries found.")
                return
            
            print("\n=== Your Beneficiaries ===")
            for beneficiary in beneficiaries:
                print(f"Name: {beneficiary['beneficiary_name']}")
                print(f"Account: {beneficiary['beneficiary_account']}")
                print(f"Bank: {beneficiary['bank_name']}")
                print(f"IFSC: {beneficiary['ifsc_code']}")
                print(f"Nickname: {beneficiary['nickname']}")
                print("-" * 30)
                
        except mysql.connector.Error as err:
            print(f"Error fetching beneficiaries: {err}")

    def transfer_money(self):
        """Transfer money to another account"""
        print("\n=== Fund Transfer ===")
        print("1. Transfer to existing beneficiary")
        print("2. Transfer to new account")
        
        choice = input("Select option (1-2): ")
        
        try:
            recipient_name = ""
            if choice == '1':
                self.view_beneficiaries()
                beneficiary_account = input("Enter beneficiary account number: ")
                
                # Get beneficiary name
                cursor = self.db_connection.cursor(dictionary=True)
                cursor.execute(
                    "SELECT beneficiary_name FROM beneficiaries WHERE beneficiary_account = %s AND user_account = %s",
                    (beneficiary_account, self.current_user['account_number'])
                )
                beneficiary = cursor.fetchone()
                cursor.close()
                
                if beneficiary:
                    recipient_name = beneficiary['beneficiary_name']
                else:
                    print("Beneficiary not found.")
                    return
            else:
                beneficiary_account = input("Enter recipient account number: ")
                recipient_name = input("Enter recipient name: ")
            
            amount = float(input("Enter amount to transfer: ₹"))
            
            if amount <= 0:
                print("Amount must be positive.")
                return
            
            # Check sufficient balance
            if self.current_user['balance'] < amount:
                print("Insufficient balance.")
                return
            
            # Check daily limit
            if not self.check_daily_limit(amount):
                print(f"Transaction exceeds daily limit of ₹{self.transaction_limit:.2f}")
                return
            
            # Verify recipient account exists
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute("SELECT name, email, balance FROM users WHERE account_number = %s", (beneficiary_account,))
            recipient = cursor.fetchone()
            cursor.close()
            
            if not recipient:
                print("Recipient account not found.")
                return
            
            # Generate transaction OTP
            otp = self.generate_otp()
            if self.store_otp(self.current_user['email'], otp, "TRANSACTION") and \
               self.send_otp_email(self.current_user['email'], otp, "TRANSACTION"):
                print("Transaction OTP sent to your email.")
                
                entered_otp = input("Enter transaction OTP: ")
                if self.verify_otp(self.current_user['email'], entered_otp, "TRANSACTION"):
                    cursor = self.db_connection.cursor()
                    
                    # Update sender balance
                    new_balance_sender = self.current_user['balance'] - amount
                    cursor.execute(
                        "UPDATE users SET balance = %s WHERE account_number = %s",
                        (new_balance_sender, self.current_user['account_number'])
                    )
                    
                    # Update recipient balance
                    new_balance_recipient = recipient['balance'] + amount
                    cursor.execute(
                        "UPDATE users SET balance = %s WHERE account_number = %s",
                        (new_balance_recipient, beneficiary_account)
                    )
                    
                    # Record transaction for sender
                    reference_number = self.generate_reference_number()
                    cursor.execute(
                        """INSERT INTO transactions 
                        (account_number, transaction_type, amount, recipient_account, recipient_name, 
                         description, reference_number, balance_after) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (self.current_user['account_number'], 'TRANSFER', amount, beneficiary_account,
                         recipient_name, f'Transfer to {beneficiary_account}', 
                         reference_number, new_balance_sender)
                    )
                    
                    # Record transaction for recipient
                    cursor.execute(
                        """INSERT INTO transactions 
                        (account_number, transaction_type, amount, recipient_account, recipient_name,
                         description, reference_number, balance_after) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (beneficiary_account, 'DEPOSIT', amount, self.current_user['account_number'],
                         self.current_user['name'], f'Transfer from {self.current_user["account_number"]}',
                         reference_number, new_balance_recipient)
                    )
                    
                    self.db_connection.commit()
                    cursor.close()
                    
                    # Update current user balance
                    self.current_user['balance'] = new_balance_sender
                    
                    print(f"Successfully transferred ₹{amount:.2f} to {beneficiary_account}")
                    print(f"Reference Number: {reference_number}")
                    self.log_audit("FUND_TRANSFER", f"Amount: ₹{amount:.2f}, To: {beneficiary_account}")
                    
                    # Send transaction alert to sender
                    alert_body_sender = f"""
                    <html>
                        <body>
                            <h3>Transaction Alert</h3>
                            <p>Dear {self.current_user['name']},</p>
                            <p>Your account has been debited with ₹{amount:.2f}</p>
                            <p><strong>To:</strong> {recipient_name} ({beneficiary_account})</p>
                            <p><strong>Reference Number:</strong> {reference_number}</p>
                            <p><strong>Available Balance:</strong> ₹{new_balance_sender:.2f}</p>
                        </body>
                    </html>
                    """
                    self.send_email(self.current_user['email'], "Transaction Alert - Transfer", alert_body_sender)
                    
                    # Send transaction alert to recipient
                    alert_body_recipient = f"""
                    <html>
                        <body>
                            <h3>Transaction Alert</h3>
                            <p>Dear {recipient['name']},</p>
                            <p>Your account has been credited with ₹{amount:.2f}</p>
                            <p><strong>From:</strong> {self.current_user['name']} ({self.current_user['account_number']})</p>
                            <p><strong>Reference Number:</strong> {reference_number}</p>
                            <p><strong>Available Balance:</strong> ₹{new_balance_recipient:.2f}</p>
                        </body>
                    </html>
                    """
                    self.send_email(recipient['email'], "Transaction Alert - Credit", alert_body_recipient)
                    
                else:
                    print("Invalid transaction OTP.")
            else:
                print("Failed to send transaction OTP.")
            
        except ValueError:
            print("Invalid amount.")
        except mysql.connector.Error as err:
            print(f"Transfer failed: {err}")

    def apply_fixed_deposit(self):
        """Apply for fixed deposit"""
        print("\n=== Fixed Deposit Application ===")
        
        try:
            amount = float(input("Enter FD amount: ₹"))
            tenure = int(input("Enter tenure in months: "))
            
            if amount <= 0 or tenure <= 0:
                print("Amount and tenure must be positive.")
                return
            
            if self.current_user['balance'] < amount:
                print("Insufficient balance for FD.")
                return
            
            # Calculate interest (6% annual)
            interest_rate = 6.0
            maturity_amount = amount * (1 + (interest_rate / 100) * (tenure / 12))
            maturity_date = datetime.now() + timedelta(days=tenure * 30)
            
            fd_number = f"FD{random.randint(1000000000, 9999999999)}"
            
            cursor = self.db_connection.cursor()
            
            # Deduct amount from balance
            new_balance = self.current_user['balance'] - amount
            cursor.execute(
                "UPDATE users SET balance = %s WHERE account_number = %s",
                (new_balance, self.current_user['account_number'])
            )
            
            # Create FD
            cursor.execute(
                """INSERT INTO fixed_deposits 
                (account_number, fd_number, amount, interest_rate, tenure_months, start_date, maturity_date, maturity_amount) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (self.current_user['account_number'], fd_number, amount, interest_rate, 
                 tenure, datetime.now().date(), maturity_date.date(), maturity_amount)
            )
            
            # Record transaction
            reference_number = self.generate_reference_number()
            cursor.execute(
                """INSERT INTO transactions 
                (account_number, transaction_type, amount, description, reference_number, balance_after) 
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (self.current_user['account_number'], 'WITHDRAWAL', amount, 
                 f'Fixed Deposit - {fd_number}', reference_number, new_balance)
            )
            
            self.db_connection.commit()
            cursor.close()
            
            self.current_user['balance'] = new_balance
            
            print(f"Fixed Deposit created successfully!")
            print(f"FD Number: {fd_number}")
            print(f"Amount: ₹{amount:.2f}")
            print(f"Interest Rate: {interest_rate}%")
            print(f"Maturity Date: {maturity_date.date()}")
            print(f"Maturity Amount: ₹{maturity_amount:.2f}")
            self.log_audit("FD_CREATED", f"Amount: ₹{amount:.2f}, FD: {fd_number}")
            
        except ValueError:
            print("Invalid input.")
        except mysql.connector.Error as err:
            print(f"FD application failed: {err}")

    def view_fixed_deposits(self):
        """View fixed deposits"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM fixed_deposits WHERE account_number = %s ORDER BY created_at DESC",
                (self.current_user['account_number'],)
            )
            
            fds = cursor.fetchall()
            cursor.close()
            
            if not fds:
                print("No fixed deposits found.")
                return
            
            print("\n=== Your Fixed Deposits ===")
            for fd in fds:
                print(f"FD Number: {fd['fd_number']}")
                print(f"Amount: ₹{fd['amount']:.2f}")
                print(f"Interest Rate: {fd['interest_rate']}%")
                print(f"Tenure: {fd['tenure_months']} months")
                print(f"Maturity Date: {fd['maturity_date']}")
                print(f"Maturity Amount: ₹{fd['maturity_amount']:.2f}")
                print(f"Status: {fd['status']}")
                print("-" * 40)
                
        except mysql.connector.Error as err:
            print(f"Error fetching FDs: {err}")

    def apply_loan(self):
        """Apply for loan"""
        print("\n=== Loan Application ===")
        print("1. Personal Loan (12% interest)")
        print("2. Home Loan (8% interest)")
        print("3. Car Loan (9% interest)")
        print("4. Education Loan (10% interest)")
        
        try:
            choice = input("Select loan type (1-4): ")
            loan_types = {
                '1': ('PERSONAL', 12.0),
                '2': ('HOME', 8.0),
                '3': ('CAR', 9.0),
                '4': ('EDUCATION', 10.0)
            }
            
            if choice not in loan_types:
                print("Invalid choice.")
                return
            
            loan_type, interest_rate = loan_types[choice]
            amount = float(input("Enter loan amount: ₹"))
            tenure = int(input("Enter tenure in months: "))
            
            if amount <= 0 or tenure <= 0:
                print("Amount and tenure must be positive.")
                return
            
            # Calculate EMI
            monthly_interest = interest_rate / 12 / 100
            emi = amount * monthly_interest * (1 + monthly_interest) ** tenure / ((1 + monthly_interest) ** tenure - 1)
            
            loan_id = f"LOAN{random.randint(1000000000, 9999999999)}"
            
            cursor = self.db_connection.cursor()
            cursor.execute(
                """INSERT INTO loans 
                (account_number, loan_id, loan_type, amount, interest_rate, tenure_months, emi_amount) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (self.current_user['account_number'], loan_id, loan_type, amount, 
                 interest_rate, tenure, emi)
            )
            
            self.db_connection.commit()
            cursor.close()
            
            print(f"Loan application submitted successfully!")
            print(f"Loan ID: {loan_id}")
            print(f"Loan Type: {loan_type}")
            print(f"Amount: ₹{amount:.2f}")
            print(f"Interest Rate: {interest_rate}%")
            print(f"Tenure: {tenure} months")
            print(f"Monthly EMI: ₹{emi:.2f}")
            print("\nNote: Your loan application is under review.")
            self.log_audit("LOAN_APPLIED", f"Amount: ₹{amount:.2f}, Type: {loan_type}")
            
        except ValueError:
            print("Invalid input.")
        except mysql.connector.Error as err:
            print(f"Loan application failed: {err}")

    def view_loans(self):
        """View loan applications"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM loans WHERE account_number = %s ORDER BY created_at DESC",
                (self.current_user['account_number'],)
            )
            
            loans = cursor.fetchall()
            cursor.close()
            
            if not loans:
                print("No loan applications found.")
                return
            
            print("\n=== Your Loans ===")
            for loan in loans:
                print(f"Loan ID: {loan['loan_id']}")
                print(f"Type: {loan['loan_type']}")
                print(f"Amount: ₹{loan['amount']:.2f}")
                print(f"Interest Rate: {loan['interest_rate']}%")
                print(f"Tenure: {loan['tenure_months']} months")
                print(f"EMI: ₹{loan['emi_amount']:.2f}")
                print(f"Status: {loan['status']}")
                if loan['disbursement_date']:
                    print(f"Disbursement Date: {loan['disbursement_date']}")
                print("-" * 40)
                
        except mysql.connector.Error as err:
            print(f"Error fetching loans: {err}")

    def manage_loans(self):
        """Manage loan applications"""
        try:
            print("\n=== Loan Management ===")
            print("1. View Pending Loans")
            print("2. View All Loans")
            print("3. Approve Loan")
            print("4. Reject Loan")
            print("5. Disburse Loan")
            
            choice = input("Select option (1-5): ")
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            if choice == '1':
                cursor.execute("""
                    SELECT l.*, u.name, u.email, u.account_number 
                    FROM loans l 
                    JOIN users u ON l.account_number = u.account_number 
                    WHERE l.status = 'PENDING' 
                    ORDER BY l.created_at DESC
                """)
            elif choice == '2':
                cursor.execute("""
                    SELECT l.*, u.name, u.email, u.account_number 
                    FROM loans l 
                    JOIN users u ON l.account_number = u.account_number 
                    ORDER BY l.created_at DESC
                """)
            elif choice in ['3', '4', '5']:
                loan_id = input("Enter Loan ID: ")
                
                if choice == '3':
                    cursor.execute(
                        "UPDATE loans SET status = 'APPROVED' WHERE loan_id = %s",
                        (loan_id,)
                    )
                    print("✓ Loan approved successfully!")
                    
                    # Send approval email
                    cursor.execute("""
                        SELECT u.email, u.name, l.loan_type, l.amount 
                        FROM loans l 
                        JOIN users u ON l.account_number = u.account_number 
                        WHERE l.loan_id = %s
                    """, (loan_id,))
                    loan = cursor.fetchone()
                    
                    if loan:
                        email_body = f"""
                        <html>
                            <body>
                                <h3>Loan Application Approved</h3>
                                <p>Dear {loan['name']},</p>
                                <p>We are pleased to inform you that your {loan['loan_type']} loan application for ₹{loan['amount']:.2f} has been approved.</p>
                                <p>Our team will contact you shortly for further process.</p>
                                <p>Thank you for choosing SecureBank!</p>
                            </body>
                        </html>
                        """
                        self.send_email(loan['email'], "Loan Application Approved", email_body)
                        
                elif choice == '4':
                    reason = input("Enter rejection reason: ")
                    cursor.execute(
                        "UPDATE loans SET status = 'REJECTED' WHERE loan_id = %s",
                        (loan_id,)
                    )
                    print("✓ Loan rejected successfully!")
                    
                    # Send rejection email
                    cursor.execute("""
                        SELECT u.email, u.name, l.loan_type, l.amount 
                        FROM loans l 
                        JOIN users u ON l.account_number = u.account_number 
                        WHERE l.loan_id = %s
                    """, (loan_id,))
                    loan = cursor.fetchone()
                    
                    if loan:
                        email_body = f"""
                        <html>
                            <body>
                                <h3>Loan Application Update</h3>
                                <p>Dear {loan['name']},</p>
                                <p>We regret to inform you that your {loan['loan_type']} loan application for ₹{loan['amount']:.2f} has been rejected.</p>
                                <p><strong>Reason:</strong> {reason}</p>
                                <p>Please contact our support team for more information.</p>
                            </body>
                        </html>
                        """
                        self.send_email(loan['email'], "Loan Application Rejected", email_body)
                        
                elif choice == '5':
                    cursor.execute(
                        "UPDATE loans SET status = 'DISBURSED', disbursement_date = %s WHERE loan_id = %s",
                        (datetime.now().date(), loan_id)
                    )
                    print("✓ Loan disbursed successfully!")
                    
                self.db_connection.commit()
                cursor.close()
                return
            else:
                print("Invalid choice.")
                return
            
            loans = cursor.fetchall()
            cursor.close()
            
            if not loans:
                print("No loans found.")
                return
            
            print(f"\n=== Loans ===")
            for loan in loans:
                print(f"Loan ID: {loan['loan_id']}")
                print(f"User: {loan['name']} ({loan['account_number']})")
                print(f"Type: {loan['loan_type']}")
                print(f"Amount: ₹{loan['amount']:.2f}")
                print(f"Interest Rate: {loan['interest_rate']}%")
                print(f"Tenure: {loan['tenure_months']} months")
                print(f"EMI: ₹{loan['emi_amount']:.2f}")
                print(f"Status: {loan['status']}")
                if loan['disbursement_date']:
                    print(f"Disbursement Date: {loan['disbursement_date']}")
                print("-" * 50)
                
        except mysql.connector.Error as err:
            print(f"Error managing loans: {err}")

    def manage_fixed_deposits(self):
        """Manage fixed deposits"""
        try:
            print("\n=== Fixed Deposit Management ===")
            print("1. View All FDs")
            print("2. Close FD")
            print("3. View Matured FDs")
            
            choice = input("Select option (1-3): ")
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            if choice == '1':
                cursor.execute("""
                    SELECT f.*, u.name, u.email, u.account_number 
                    FROM fixed_deposits f 
                    JOIN users u ON f.account_number = u.account_number 
                    ORDER BY f.created_at DESC
                """)
            elif choice == '2':
                fd_number = input("Enter FD Number: ")
                cursor.execute(
                    "UPDATE fixed_deposits SET status = 'CLOSED' WHERE fd_number = %s",
                    (fd_number,)
                )
                self.db_connection.commit()
                cursor.close()
                print("✓ FD closed successfully!")
                return
            elif choice == '3':
                cursor.execute("""
                    SELECT f.*, u.name, u.email, u.account_number 
                    FROM fixed_deposits f 
                    JOIN users u ON f.account_number = u.account_number 
                    WHERE f.maturity_date <= %s AND f.status = 'ACTIVE'
                    ORDER BY f.maturity_date DESC
                """, (datetime.now().date(),))
            else:
                print("Invalid choice.")
                return
            
            fds = cursor.fetchall()
            cursor.close()
            
            if not fds:
                print("No fixed deposits found.")
                return
            
            print(f"\n=== Fixed Deposits ===")
            for fd in fds:
                print(f"FD Number: {fd['fd_number']}")
                print(f"User: {fd['name']} ({fd['account_number']})")
                print(f"Amount: ₹{fd['amount']:.2f}")
                print(f"Interest Rate: {fd['interest_rate']}%")
                print(f"Tenure: {fd['tenure_months']} months")
                print(f"Start Date: {fd['start_date']}")
                print(f"Maturity Date: {fd['maturity_date']}")
                print(f"Maturity Amount: ₹{fd['maturity_amount']:.2f}")
                print(f"Status: {fd['status']}")
                print("-" * 50)
                
        except mysql.connector.Error as err:
            print(f"Error managing FDs: {err}")

    def view_all_users(self):
        """View all users with pagination"""
        try:
            page = int(input("Enter page number (1-∞): ") or 1)
            limit = 10
            offset = (page - 1) * limit
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            # Get total count
            cursor.execute("SELECT COUNT(*) as total FROM users")
            total = cursor.fetchone()['total']
            
            # Get users
            cursor.execute("""
                SELECT id, account_number, name, email, phone, account_type, 
                       balance, status, last_login, created_at 
                FROM users 
                ORDER BY created_at DESC 
                LIMIT %s OFFSET %s
            """, (limit, offset))
            
            users = cursor.fetchall()
            cursor.close()
            
            print(f"\n=== All Users (Page {page}) ===")
            print(f"Total Users: {total}")
            print(f"Showing {len(users)} users\n")
            
            for user in users:
                print(f"Account: {user['account_number']}")
                print(f"Name: {user['name']}")
                print(f"Email: {user['email']}")
                print(f"Type: {user['account_type']}")
                print(f"Balance: ₹{user['balance']:.2f}")
                print(f"Status: {user['status']}")
                print(f"Last Login: {user['last_login']}")
                print("-" * 50)
                
        except ValueError:
            print("Invalid page number.")
        except mysql.connector.Error as err:
            print(f"Error fetching users: {err}")

    def view_all_transactions(self):
        """View all transactions with filters"""
        try:
            print("\n=== Transaction Filters ===")
            print("1. All transactions")
            print("2. Today's transactions")
            print("3. Date range")
            print("4. By account number")
            
            choice = input("Select option (1-4): ")
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            if choice == '1':
                cursor.execute("""
                    SELECT t.*, u.name as user_name 
                    FROM transactions t 
                    JOIN users u ON t.account_number = u.account_number 
                    ORDER BY t.transaction_date DESC 
                    LIMIT 50
                """)
            elif choice == '2':
                today = datetime.now().date()
                cursor.execute("""
                    SELECT t.*, u.name as user_name 
                    FROM transactions t 
                    JOIN users u ON t.account_number = u.account_number 
                    WHERE DATE(t.transaction_date) = %s 
                    ORDER BY t.transaction_date DESC
                """, (today,))
            elif choice == '3':
                start_date = input("Enter start date (YYYY-MM-DD): ")
                end_date = input("Enter end date (YYYY-MM-DD): ")
                cursor.execute("""
                    SELECT t.*, u.name as user_name 
                    FROM transactions t 
                    JOIN users u ON t.account_number = u.account_number 
                    WHERE DATE(t.transaction_date) BETWEEN %s AND %s 
                    ORDER BY t.transaction_date DESC
                """, (start_date, end_date))
            elif choice == '4':
                account_number = input("Enter account number: ")
                cursor.execute("""
                    SELECT t.*, u.name as user_name 
                    FROM transactions t 
                    JOIN users u ON t.account_number = u.account_number 
                    WHERE t.account_number = %s 
                    ORDER BY t.transaction_date DESC
                """, (account_number,))
            else:
                print("Invalid choice.")
                return
            
            transactions = cursor.fetchall()
            cursor.close()
            
            if not transactions:
                print("No transactions found.")
                return
            
            print(f"\n=== Transactions ===")
            total_amount = 0
            for transaction in transactions:
                print(f"Date: {transaction['transaction_date']}")
                print(f"User: {transaction['user_name']} ({transaction['account_number']})")
                print(f"Type: {transaction['transaction_type']}")
                print(f"Amount: ₹{transaction['amount']:.2f}")
                print(f"Reference: {transaction['reference_number']}")
                if transaction['recipient_account']:
                    print(f"Recipient: {transaction['recipient_name']} ({transaction['recipient_account']})")
                print(f"Balance After: ₹{transaction['balance_after']:.2f}")
                print("-" * 50)
                total_amount += transaction['amount']
            
            print(f"Total Amount: ₹{total_amount:.2f}")
                
        except mysql.connector.Error as err:
            print(f"Error fetching transactions: {err}")

    def manage_user_account(self):
        """Manage user accounts (activate/deactivate)"""
        print("\n=== Manage User Account ===")
        
        account_number = input("Enter account number: ")
        
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM users WHERE account_number = %s",
                (account_number,)
            )
            user = cursor.fetchone()
            cursor.close()
            
            if not user:
                print("User not found.")
                return
            
            print(f"\nUser Details:")
            print(f"Name: {user['name']}")
            print(f"Email: {user['email']}")
            print(f"Current Status: {user['status']}")
            print(f"Balance: ₹{user['balance']:.2f}")
            
            print("\n1. Activate Account")
            print("2. Deactivate Account")
            print("3. Reset Password")
            print("4. View Full Details")
            
            choice = input("Select option (1-4): ")
            
            cursor = self.db_connection.cursor()
            
            if choice == '1':
                cursor.execute(
                    "UPDATE users SET status = 'ACTIVE' WHERE account_number = %s",
                    (account_number,)
                )
                print("✓ Account activated successfully.")
                
            elif choice == '2':
                cursor.execute(
                    "UPDATE users SET status = 'INACTIVE' WHERE account_number = %s",
                    (account_number,)
                )
                print("✓ Account deactivated successfully.")
                
            elif choice == '3':
                new_password = getpass.getpass("Enter new password: ")
                confirm_password = getpass.getpass("Confirm new password: ")
                
                if new_password == confirm_password:
                    cursor.execute(
                        "UPDATE users SET password = %s WHERE account_number = %s",
                        (self.hash_password(new_password), account_number)
                    )
                    print("✓ Password reset successfully.")
                else:
                    print("Passwords do not match.")
                    return
                    
            elif choice == '4':
                print(f"\nFull User Details:")
                for key, value in user.items():
                    print(f"{key}: {value}")
                return
            else:
                print("Invalid choice.")
                return
            
            self.db_connection.commit()
            cursor.close()
            self.log_audit("ADMIN_USER_MANAGEMENT", f"Action {choice} on account {account_number}")
            
        except mysql.connector.Error as err:
            print(f"Error managing user: {err}")

    def system_statistics(self):
        """Display system statistics"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            
            # Total users
            cursor.execute("SELECT COUNT(*) as total_users FROM users")
            total_users = cursor.fetchone()['total_users']
            
            # Active users
            cursor.execute("SELECT COUNT(*) as active_users FROM users WHERE status = 'ACTIVE'")
            active_users = cursor.fetchone()['active_users']
            
            # Total balance
            cursor.execute("SELECT SUM(balance) as total_balance FROM users WHERE status = 'ACTIVE'")
            total_balance = cursor.fetchone()['total_balance'] or 0
            
            # Today's transactions
            today = datetime.now().date()
            cursor.execute("""
                SELECT COUNT(*) as today_txns, COALESCE(SUM(amount), 0) as today_amount 
                FROM transactions 
                WHERE DATE(transaction_date) = %s
            """, (today,))
            today_stats = cursor.fetchone()
            
            # Total transactions
            cursor.execute("SELECT COUNT(*) as total_txns FROM transactions")
            total_txns = cursor.fetchone()['total_txns']
            
            # Active FDs
            cursor.execute("SELECT COUNT(*) as active_fds, COALESCE(SUM(amount), 0) as fd_amount FROM fixed_deposits WHERE status = 'ACTIVE'")
            fd_stats = cursor.fetchone()
            
            # Pending loans
            cursor.execute("SELECT COUNT(*) as pending_loans, COALESCE(SUM(amount), 0) as loan_amount FROM loans WHERE status = 'PENDING'")
            loan_stats = cursor.fetchone()
            
            cursor.close()
            
            print("\n=== System Statistics ===")
            print(f"Total Users: {total_users}")
            print(f"Active Users: {active_users}")
            print(f"Total Balance: ₹{total_balance:.2f}")
            print(f"Today's Transactions: {today_stats['today_txns']} (₹{today_stats['today_amount']:.2f})")
            print(f"Total Transactions: {total_txns}")
            print(f"Active Fixed Deposits: {fd_stats['active_fds']} (₹{fd_stats['fd_amount']:.2f})")
            print(f"Pending Loans: {loan_stats['pending_loans']} (₹{loan_stats['loan_amount']:.2f})")
            
        except mysql.connector.Error as err:
            print(f"Error fetching statistics: {err}")

    def manage_system_settings(self):
        """Manage system settings"""
        try:
            cursor = self.db_connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM system_settings")
            settings = cursor.fetchall()
            cursor.close()
            
            print("\n=== System Settings ===")
            for setting in settings:
                print(f"{setting['setting_key']}: {setting['setting_value']} - {setting['description']}")
            
            print("\n1. Update Setting")
            print("2. Add New Setting")
            print("3. Back")
            
            choice = input("Select option (1-3): ")
            
            if choice == '1':
                key = input("Enter setting key to update: ")
                new_value = input("Enter new value: ")
                
                cursor = self.db_connection.cursor()
                cursor.execute(
                    "UPDATE system_settings SET setting_value = %s WHERE setting_key = %s",
                    (new_value, key)
                )
                self.db_connection.commit()
                cursor.close()
                
                if cursor.rowcount > 0:
                    print("✓ Setting updated successfully.")
                    # Update transaction limit if changed
                    if key == 'daily_transaction_limit':
                        self.transaction_limit = float(new_value)
                else:
                    print("Setting not found.")
                    
            elif choice == '2':
                key = input("Enter new setting key: ")
                value = input("Enter setting value: ")
                description = input("Enter description: ")
                
                cursor = self.db_connection.cursor()
                cursor.execute(
                    "INSERT INTO system_settings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
                    (key, value, description)
                )
                self.db_connection.commit()
                cursor.close()
                print("✓ New setting added successfully.")
                
        except mysql.connector.Error as err:
            print(f"Error managing settings: {err}")

    def view_audit_logs(self):
        """View audit logs"""
        try:
            print("\n=== Audit Logs ===")
            print("1. Last 50 logs")
            print("2. Date range")
            print("3. By action type")
            
            choice = input("Select option (1-3): ")
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            if choice == '1':
                cursor.execute("""
                    SELECT a.*, u.name, u.account_number 
                    FROM audit_log a 
                    LEFT JOIN users u ON a.user_id = u.id 
                    ORDER BY a.created_at DESC 
                    LIMIT 50
                """)
            elif choice == '2':
                start_date = input("Enter start date (YYYY-MM-DD): ")
                end_date = input("Enter end date (YYYY-MM-DD): ")
                cursor.execute("""
                    SELECT a.*, u.name, u.account_number 
                    FROM audit_log a 
                    LEFT JOIN users u ON a.user_id = u.id 
                    WHERE DATE(a.created_at) BETWEEN %s AND %s 
                    ORDER BY a.created_at DESC
                """, (start_date, end_date))
            elif choice == '3':
                action = input("Enter action type: ")
                cursor.execute("""
                    SELECT a.*, u.name, u.account_number 
                    FROM audit_log a 
                    LEFT JOIN users u ON a.user_id = u.id 
                    WHERE a.action LIKE %s 
                    ORDER BY a.created_at DESC
                """, (f'%{action}%',))
            else:
                print("Invalid choice.")
                return
            
            logs = cursor.fetchall()
            cursor.close()
            
            if not logs:
                print("No audit logs found.")
                return
            
            print(f"\n=== Audit Logs ===")
            for log in logs:
                user_info = f"{log['name']} ({log['account_number']})" if log['name'] else "System"
                print(f"Date: {log['created_at']}")
                print(f"User: {user_info}")
                print(f"Action: {log['action']}")
                print(f"Description: {log['description']}")
                print("-" * 50)
                
        except mysql.connector.Error as err:
            print(f"Error fetching audit logs: {err}")

    def transaction_history(self):
        """View detailed transaction history"""
        try:
            print("\n=== Transaction History ===")
            print("1. Last 10 transactions")
            print("2. Custom date range")
            
            choice = input("Select option (1-2): ")
            
            cursor = self.db_connection.cursor(dictionary=True)
            
            if choice == '1':
                cursor.execute(
                    """SELECT * FROM transactions 
                    WHERE account_number = %s 
                    ORDER BY transaction_date DESC LIMIT 10""",
                    (self.current_user['account_number'],)
                )
            else:
                start_date = input("Enter start date (YYYY-MM-DD): ")
                end_date = input("Enter end date (YYYY-MM-DD): ")
                cursor.execute(
                    """SELECT * FROM transactions 
                    WHERE account_number = %s AND DATE(transaction_date) BETWEEN %s AND %s 
                    ORDER BY transaction_date DESC""",
                    (self.current_user['account_number'], start_date, end_date)
                )
            
            transactions = cursor.fetchall()
            cursor.close()
            
            if not transactions:
                print("No transactions found.")
                return
            
            print(f"\n=== Transaction History for {self.current_user['name']} ===")
            total_debit = 0
            total_credit = 0
            
            for transaction in transactions:
                print(f"Date: {transaction['transaction_date']}")
                print(f"Type: {transaction['transaction_type']}")
                print(f"Amount: ₹{transaction['amount']:.2f}")
                
                if transaction['transaction_type'] in ['WITHDRAWAL', 'TRANSFER']:
                    total_debit += transaction['amount']
                else:
                    total_credit += transaction['amount']
                
                if transaction['recipient_account']:
                    print(f"To/From: {transaction['recipient_name']} ({transaction['recipient_account']})")
                print(f"Reference: {transaction['reference_number']}")
                if transaction['balance_after']:
                    print(f"Balance After: ₹{transaction['balance_after']:.2f}")
                print(f"Description: {transaction['description']}")
                print("-" * 50)
            
            print(f"\nSummary:")
            print(f"Total Credit: ₹{total_credit:.2f}")
            print(f"Total Debit: ₹{total_debit:.2f}")
            print(f"Net: ₹{total_credit - total_debit:.2f}")
                
        except mysql.connector.Error as err:
            print(f"Error fetching transaction history: {err}")

    def update_profile(self):
        """Update user profile"""
        print("\n=== Update Profile ===")
        print("1. Update Phone")
        print("2. Update Address")
        print("3. Change Password")
        
        choice = input("Select option (1-3): ")
        
        try:
            cursor = self.db_connection.cursor()
            
            if choice == '1':
                new_phone = input("Enter new phone number: ")
                if not self.validate_phone(new_phone):
                    print("Invalid phone number.")
                    return
                
                cursor.execute(
                    "UPDATE users SET phone = %s WHERE account_number = %s",
                    (new_phone, self.current_user['account_number'])
                )
                print("Phone number updated successfully.")
                
            elif choice == '2':
                new_address = input("Enter new address: ")
                cursor.execute(
                    "UPDATE users SET address = %s WHERE account_number = %s",
                    (new_address, self.current_user['account_number'])
                )
                print("Address updated successfully.")
                
            elif choice == '3':
                current_password = getpass.getpass("Enter current password: ")
                if self.hash_password(current_password) != self.current_user['password']:
                    print("Current password is incorrect.")
                    return
                
                new_password = getpass.getpass("Enter new password: ")
                confirm_password = getpass.getpass("Confirm new password: ")
                
                if new_password != confirm_password:
                    print("Passwords do not match.")
                    return
                
                cursor.execute(
                    "UPDATE users SET password = %s WHERE account_number = %s",
                    (self.hash_password(new_password), self.current_user['account_number'])
                )
                print("Password changed successfully.")
                
            else:
                print("Invalid choice.")
                return
            
            self.db_connection.commit()
            cursor.close()
            self.log_audit("PROFILE_UPDATED", f"Updated {['phone', 'address', 'password'][int(choice)-1]}")
            
        except mysql.connector.Error as err:
            print(f"Profile update failed: {err}")

    def user_menu(self):
        """Enhanced user menu"""
        while True:
            print(f"\n=== Welcome, {self.current_user['name']} ===")
            print("1. Account Summary")
            print("2. Deposit Money")
            print("3. Withdraw Money")
            print("4. Fund Transfer")
            print("5. Add Beneficiary")
            print("6. View Beneficiaries")
            print("7. Fixed Deposit")
            print("8. Loan Services")
            print("9. Transaction History")
            print("10. Update Profile")
            print("11. Logout")
            
            choice = input("Enter your choice (1-11): ")
            
            if choice == '1':
                self.check_balance()
            elif choice == '2':
                self.deposit()
            elif choice == '3':
                self.withdraw()
            elif choice == '4':
                self.transfer_money()
            elif choice == '5':
                self.add_beneficiary()
            elif choice == '6':
                self.view_beneficiaries()
            elif choice == '7':
                self.fd_menu()
            elif choice == '8':
                self.loan_menu()
            elif choice == '9':
                self.transaction_history()
            elif choice == '10':
                self.update_profile()
            elif choice == '11':
                print("Logged out successfully.")
                self.log_audit("USER_LOGOUT", "User logged out")
                break
            else:
                print("Invalid choice. Please try again.")

    def fd_menu(self):
        """Fixed Deposit menu"""
        while True:
            print("\n=== Fixed Deposit Services ===")
            print("1. Apply for Fixed Deposit")
            print("2. View Fixed Deposits")
            print("3. Back to Main Menu")
            
            choice = input("Enter your choice (1-3): ")
            
            if choice == '1':
                self.apply_fixed_deposit()
            elif choice == '2':
                self.view_fixed_deposits()
            elif choice == '3':
                break
            else:
                print("Invalid choice.")

    def loan_menu(self):
        """Loan services menu"""
        while True:
            print("\n=== Loan Services ===")
            print("1. Apply for Loan")
            print("2. View Loan Applications")
            print("3. Back to Main Menu")
            
            choice = input("Enter your choice (1-3): ")
            
            if choice == '1':
                self.apply_loan()
            elif choice == '2':
                self.view_loans()
            elif choice == '3':
                break
            else:
                print("Invalid choice.")

    def admin_menu(self):
        """Admin menu"""
        while True:
            print(f"\n=== Admin Panel - Welcome {self.current_admin['username']} ===")
            print("1. View All Users")
            print("2. View All Transactions")
            print("3. Manage User Account")
            print("4. System Statistics")
            print("5. System Settings")
            print("6. Loan Management")
            print("7. Fixed Deposit Management")
            print("8. Audit Logs")
            print("9. Logout")
            
            choice = input("Enter your choice (1-9): ")
            
            if choice == '1':
                self.view_all_users()
            elif choice == '2':
                self.view_all_transactions()
            elif choice == '3':
                self.manage_user_account()
            elif choice == '4':
                self.system_statistics()
            elif choice == '5':
                self.manage_system_settings()
            elif choice == '6':
                self.manage_loans()
            elif choice == '7':
                self.manage_fixed_deposits()
            elif choice == '8':
                self.view_audit_logs()
            elif choice == '9':
                print("Admin logged out successfully.")
                self.current_admin = None
                break
            else:
                print("Invalid choice. Please try again.")

    def run(self):
        """Main application runner"""
        print('''=== Welcome to secure Bank App ===
Made By:Rupesh,Jayaraju,Pranathi,Pooja''')
        
        # Create tables if they don't exist
        if self.db_connection:
            self.create_tables()
            self.create_admin_tables()
        else:
            print("Failed to connect to database. Please check your MySQL setup.")
            return
        
        while True:
            print("\n1. User Registration")
            print("2. User Login with OTP")
            print("3. Admin Login")
            print("4. Exit")
            
            choice = input("Enter your choice (1-4): ")
            
            if choice == '1':
                self.register_user()
            elif choice == '2':
                user = self.login_with_otp()
                if user:
                    self.user_menu()
            elif choice == '3':
                if self.admin_login():
                    self.admin_menu()
            elif choice == '4':
                print("Thank you for using Secure Bank App!")
                if self.db_connection:
                    self.db_connection.close()
                break
            else:
                print("Invalid choice. Please try again.")

if __name__ == "__main__":
    app = EnhancedBankApp()
    app.run()
