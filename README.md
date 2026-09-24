# Shree Sagarmatha Secondary School & Sagarmatha EMS

**School Name**: Shree Sagarmatha Secondary School (श्री सगरमाथा माध्यमिक विद्यालय)  
**Location**: Bhadrapur Municipality - Ward No. 2, Sagarmatha, Jhapa, Koshi Province, Nepal  
**Established**: 2034 B.S. (1977 A.D.)  
**Type**: Centrally Located Community Secondary School (सामुदायिक माध्यमिक विद्यालय)  
**Levels**: Early Childhood Development (ECD) to Class 12 (+2 Science, Management & Education)  
**Software**: Sagarmatha EMS (Education Management System) with Multi-Tier RBAC  

---

## 🔐 Multi-Tier Role-Based Access Control (RBAC) & Accounts

The EMS is protected with username and password authentication, PBKDF2-SHA256 password hashing with random salt, and token session management.

### Pre-Configured Demo Accounts

| Role | Username | Password | Full Name & Designation | Accessible Modules |
| :--- | :--- | :--- | :--- | :--- |
| **Admin / Headmaster** | `admin` | `admin123` | Ram Prasad Adhikari (Principal) | **Full unrestricted access**: SIS, Exams & CDC Grade Sheets, Finance & Billing, Expenses, Faculty, Attendance, Notices, Inquiries, User Accounts. |
| **Teacher / Exam Head** | `teacher` | `teacher123` | Dr. Janak Raj Bhattarai (Exam Coordinator) | Student Directory (view-only), Bulk Marks Entry, CDC Grade Sheets, Tabulation Ledger, Attendance, Notices. *(Finance & Billing hidden and blocked)*. |
| **Accountant / Bursar** | `accountant` | `account123` | Manoj Kumar Shrestha (Senior Bursar) | Student Billing, Invoices, Fee Collection Counter, Printable Receipts, Expense Log, Financial Summary. *(Exam marks editing hidden and blocked)*. |
| **Student / Parent** | `student10` | `student123` | Aayush Adhikari (Class 10 Student) | **Personalized Student Portal**: Personal Profile & ID Card, Certified Terminal CDC Grade Sheets (with QR code), Fee Dues & Payment Receipts, Attendance Summary. *(Administrative tools hidden and blocked)*. |
| **Student (NG Case)** | `student_ng` | `student123` | Pooja Dahal (Class 10 Student) | Demonstrates Nepal CDC Non-Graded (NG) condition and re-examination eligibility remarks. |

---

## 🌟 Key Features

### 1. Public School Website
- **School Profile**: Showcases history since 2034 B.S. in Bhadrapur-2, Jhapa, community mission, Principal's message, and School Management Committee (SMC / वि.व्य.स.) messages.
- **Academic Wings (ECD to 12)**:
  - Foundation (ECD & Primary 1-5 with government Midday Meal / दिवा खाजा)
  - Basic Level (Class 6–8)
  - Secondary SEE Level (Class 9–10)
  - Higher Secondary (+2) Streams (Science, Management, Education)
- **Infrastructure**: ICT Computer Lab (30+ PCs), modern Physics/Chemistry/Biology labs, library, sports grounds, and RO drinking water.
- **Notice Board**: Categorized updates (Exam routines, Admissions, General) with download attachments.
- **Online Admission Inquiry**: Real-time interactive form that logs prospective student applications directly into Sagarmatha EMS.
- **Secure Portal Gateway**: Protected login entry into **Sagarmatha EMS**.

### 2. Sagarmatha EMS (Education Management System)
- **Student Information System (SIS)**: Dual B.S./A.D. dates of birth, class & section allocations, parent contacts, blood groups, and printable Student Identity Cards (ID Cards).
- **Nepal CDC Letter Grading Directive 2078/2080 (अक्षरांकन पद्धति)**:
  - $A+$ (4.0), $A$ (3.6), $B+$ (3.2), $B$ (2.8), $C+$ (2.4), $C$ (2.0), $D$ (1.6), $NG$ (Non-Graded).
  - Enforces CDC passing rules: minimum 35% in Theory ($TH$) and minimum 40% in Practical ($PR$).
  - Bulk marks spreadsheet entry, official printable grade sheets (लब्धाङ्क पत्र) with QR code, and class tabulation ledger.
- **Finance & Fee Management**: Class fee structures, bulk invoice generator, fee collection counter with official printable fee receipts (रसिद), and school expense tracker.
- **Teacher & Attendance Management**: Faculty directory and daily student attendance register.

---

## 🚀 How to Run the Application

The system is built entirely on the Python 3 standard library (`http.server`, `sqlite3`, `json`, `hashlib`, `secrets`) and has **zero external package dependencies**.

```bash
# Navigate to the project directory
cd /Users/phadin/.gemini/antigravity/scratch/shree_sagarmatha_ems

# Run the automated verification test suites (20 tests)
python3 test_app.py
python3 test_server_handler.py
python3 test_rbac.py

# Start the server
python3 app.py
```

Open your web browser and visit:  
👉 **http://127.0.0.1:8000**

---

## 🚀 Free Cloud Deployment (Render.com)

This application is ready to deploy directly from GitHub to [Render.com](https://render.com) for free:

1. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Shree Sagarmatha Secondary School & EMS"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<repo-name>.git
   git push -u origin main
   ```

2. **Deploy on Render**:
   - Go to [dashboard.render.com](https://dashboard.render.com/) and sign in with GitHub.
   - Click **New +** → **Web Service**.
   - Connect your GitHub repository.
   - Settings:
     - **Runtime:** `Python 3`
     - **Build Command:** `python3 seed_data.py`
     - **Start Command:** `python3 app.py`
     - **Instance Type:** `Free`
   - Click **Deploy Web Service**!
   - Your school website and EMS will be live with a free SSL HTTPS address in less than 60 seconds.
