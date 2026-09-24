"""
seed_data.py - Populates Shree Sagarmatha Secondary School EMS with realistic data
"""

import os
import sqlite3
from database import init_db, get_db_connection, calculate_subject_evaluation

def seed_database(force=False):
    init_db()
    conn = get_db_connection()
    cur = conn.cursor()

    # Safety check: do not overwrite existing database in production unless forced
    try:
        cur.execute("SELECT COUNT(*) as count FROM users;")
        row = cur.fetchone()
        if row and row['count'] > 0 and not force and os.environ.get("FORCE_SEED") != "1":
            print("Database already contains data. Skipping re-seed to protect live records. (Set FORCE_SEED=1 to reset)")
            conn.close()
            return
    except sqlite3.OperationalError:
        pass

    cur.execute("PRAGMA foreign_keys = OFF;")

    # 1. School Info
    cur.execute("DELETE FROM school_info;")
    cur.execute("""
    INSERT INTO school_info (
        id, name_en, name_np, tagline_en, tagline_np,
        address_en, address_np, established_bs, email, phone, website, academic_year
    ) VALUES (
        1,
        'Shree Sagarmatha Secondary School',
        'श्री सगरमाथा माध्यमिक विद्यालय',
        'Centrally Located Community School Dedicated to Academic Excellence & Holistic Growth',
        'सामुदायिक शिक्षामा उत्कृष्टता, प्रविधिमैत्री सिकाइ र समग्र विकास',
        'Bhadrapur-2, Sagarmatha, Jhapa, Koshi Province, Nepal',
        'भद्रपुर-२, सगरमाथा, झापा, कोशी प्रदेश, नेपाल',
        2034,
        'info@sagarmathaschool.edu.np',
        '023-520134, 9842601234',
        'www.sagarmathaschool.edu.np',
        '2081'
    );
    """)

    # 2. Classes (ECD to Class 12)
    classes_data = [
        ('ECD', 'ECD', 0, 'General'),
        ('Class 1', 'Primary', 1, 'General'),
        ('Class 2', 'Primary', 2, 'General'),
        ('Class 3', 'Primary', 3, 'General'),
        ('Class 4', 'Primary', 4, 'General'),
        ('Class 5', 'Primary', 5, 'General'),
        ('Class 6', 'Basic', 6, 'General'),
        ('Class 7', 'Basic', 7, 'General'),
        ('Class 8', 'Basic', 8, 'General'),
        ('Class 9', 'Secondary', 9, 'General'),
        ('Class 10', 'Secondary', 10, 'General'),
        ('Class 11 Science', 'Higher Secondary', 11, 'Science'),
        ('Class 11 Management', 'Higher Secondary', 11, 'Management'),
        ('Class 11 Education', 'Higher Secondary', 11, 'Education'),
        ('Class 12 Science', 'Higher Secondary', 12, 'Science'),
        ('Class 12 Management', 'Higher Secondary', 12, 'Management'),
        ('Class 12 Education', 'Higher Secondary', 12, 'Education'),
    ]
    cur.executemany("INSERT OR IGNORE INTO classes (name, level, numeric_level, stream) VALUES (?, ?, ?, ?);", classes_data)

    # Fetch class IDs
    cur.execute("SELECT id, name FROM classes;")
    class_map = {row['name']: row['id'] for row in cur.fetchall()}
    c10_id = class_map.get('Class 10')
    c9_id = class_map.get('Class 9')
    c8_id = class_map.get('Class 8')
    c11_sci_id = class_map.get('Class 11 Science')
    c11_mgmt_id = class_map.get('Class 11 Management')

    # 3. Sections
    sections_data = []
    for cname, cid in class_map.items():
        sections_data.append((cid, 'A'))
        if cname in ['Class 8', 'Class 9', 'Class 10']:
            sections_data.append((cid, 'B'))
    cur.executemany("INSERT OR IGNORE INTO sections (class_id, name) VALUES (?, ?);", sections_data)

    cur.execute("SELECT id, class_id, name FROM sections;")
    section_rows = cur.fetchall()
    section_map = {}
    for row in section_rows:
        section_map[f"{row['class_id']}_{row['name']}"] = row['id']

    # 4. Comprehensive Nepal CDC Curriculum Subjects for All 17 Classes (ECD to Class 12)
    # Helper to generate subject lists
    all_subjects = []

    # ECD (Early Childhood Development / बाल विकास)
    if 'ECD' in class_map:
        cid = class_map['ECD']
        all_subjects.extend([
            (cid, 'ECD.001', 'Physical & Motor Development', 'शारीरिक तथा गतिसम्बन्धी विकास', 4.0, 0.0, 0.0, 100.0, 40.0, 0),
            (cid, 'ECD.002', 'Socio-Emotional Development', 'सामाजिक तथा संवेगात्मक विकास', 4.0, 0.0, 0.0, 100.0, 40.0, 0),
            (cid, 'ECD.003', 'Language & Communication Skills', 'भाषिक तथा सञ्चार सीप', 4.0, 0.0, 0.0, 100.0, 40.0, 0),
            (cid, 'ECD.004', 'Cognitive & Pre-Math Skills', 'बौद्धिक तथा प्रारम्भिक गणितीय सीप', 4.0, 0.0, 0.0, 100.0, 40.0, 0),
            (cid, 'ECD.005', 'Creative Arts & Expression', 'सिर्जनात्मक कला तथा अभिव्यक्ति', 4.0, 0.0, 0.0, 100.0, 40.0, 0),
        ])

    # Class 1 to Class 3 (Primary Integrated Curriculum / एकीकृत पाठ्यक्रम)
    for c_grade in [1, 2, 3]:
        cname = f'Class {c_grade}'
        if cname in class_map:
            cid = class_map[cname]
            all_subjects.extend([
                (cid, f'Nep.{c_grade}01', 'Compulsory Nepali', 'नेपाली', 5.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Eng.{c_grade}02', 'Compulsory English', 'अंग्रेजी', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Mth.{c_grade}03', 'Compulsory Mathematics', 'गणित', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Ser.{c_grade}04', 'Our Surroundings (Hamro Serophero)', 'हाम्रो सेरोफेरो', 8.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Loc.{c_grade}05', 'Local Curriculum / Mother Tongue', 'स्थानीय विषय / मातृभाषा', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
            ])

    # Class 4 & Class 5 (Primary Curriculum)
    for c_grade in [4, 5]:
        cname = f'Class {c_grade}'
        if cname in class_map:
            cid = class_map[cname]
            all_subjects.extend([
                (cid, f'Nep.{c_grade}01', 'Compulsory Nepali', 'नेपाली', 5.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Eng.{c_grade}02', 'Compulsory English', 'अंग्रेजी', 5.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Mth.{c_grade}03', 'Compulsory Mathematics', 'गणित', 5.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Sci.{c_grade}04', 'Science & Technology', 'विज्ञान तथा प्रविधि', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Soc.{c_grade}05', 'Social Studies & Human Values', 'सामाजिक अध्ययन तथा मानव मूल्य', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Hpc.{c_grade}06', 'Health, Physical & Creative Arts', 'स्वास्थ्य, शारीरिक तथा सिर्जनात्मक कला', 3.0, 30.0, 11.0, 70.0, 28.0, 0),
                (cid, f'Loc.{c_grade}07', 'Local Curriculum', 'स्थानीय पाठ्यक्रम', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
            ])

    # Class 6 & Class 7 (Basic Level / आधारभूत तह)
    for c_grade in [6, 7]:
        cname = f'Class {c_grade}'
        if cname in class_map:
            cid = class_map[cname]
            all_subjects.extend([
                (cid, f'Nep.{c_grade}01', 'Compulsory Nepali', 'नेपाली', 5.0, 75.0, 27.0, 25.0, 10.0, 0),
                (cid, f'Eng.{c_grade}02', 'Compulsory English', 'अंग्रेजी', 5.0, 75.0, 27.0, 25.0, 10.0, 0),
                (cid, f'Mth.{c_grade}03', 'Compulsory Mathematics', 'गणित', 5.0, 75.0, 27.0, 25.0, 10.0, 0),
                (cid, f'Sci.{c_grade}04', 'Science & Technology', 'विज्ञान तथा प्रविधि', 5.0, 50.0, 18.0, 50.0, 20.0, 0),
                (cid, f'Soc.{c_grade}05', 'Social Studies & Human Values', 'सामाजिक अध्ययन तथा मानव मूल्य', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
                (cid, f'Hpc.{c_grade}06', 'Health, Physical & Creative Arts', 'स्वास्थ्य, शारीरिक तथा सिर्जनात्मक कला', 3.0, 30.0, 11.0, 70.0, 28.0, 0),
                (cid, f'Loc.{c_grade}07', 'Local Curriculum / Computer Education', 'स्थानीय विषय / कम्प्युटर शिक्षा', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
            ])

    # Class 8 (BLE / Basic Level Examination - आधारभूत तह परीक्षा)
    if 'Class 8' in class_map:
        cid = class_map['Class 8']
        all_subjects.extend([
            (cid, 'Nep.801', 'Compulsory Nepali', 'नेपाली', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Eng.802', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mth.803', 'Compulsory Mathematics', 'गणित', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Sci.804', 'Science & Technology', 'विज्ञान तथा प्रविधि', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
            (cid, 'Soc.805', 'Social Studies & Moral Education', 'सामाजिक तथा नैतिक शिक्षा', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Hpe.806', 'Health, Physical & Creative Arts', 'स्वास्थ्य, शारीरिक तथा सिर्जनात्मक कला', 3.0, 30.0, 11.0, 70.0, 28.0, 0),
            (cid, 'Opt.807', 'Optional Computer / Local Subject', 'ऐच्छिक कम्प्युटर / स्थानीय विषय', 4.0, 50.0, 18.0, 50.0, 20.0, 1),
        ])

    # Class 9 (Secondary Level / SEE Foundation)
    if 'Class 9' in class_map:
        cid = class_map['Class 9']
        all_subjects.extend([
            (cid, 'Nep.901', 'Compulsory Nepali', 'नेपाली', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Eng.902', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mth.903', 'Compulsory Mathematics', 'गणित', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Sci.904', 'Science & Technology', 'विज्ञान तथा प्रविधि', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.905', 'Social Studies & Human Values', 'सामाजिक अध्ययन तथा मानव मूल्य', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Opt.906', 'Optional I (Economics)', 'ऐच्छिक प्रथम (अर्थशास्त्र)', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
            (cid, 'Opt.907', 'Optional II (Computer Science)', 'ऐच्छिक द्वितीय (कम्प्युटर विज्ञान)', 4.0, 50.0, 18.0, 50.0, 20.0, 1),
        ])

    # Class 10 (SEE CDC Curriculum 2078/2080)
    if 'Class 10' in class_map:
        cid = class_map['Class 10']
        all_subjects.extend([
            (cid, 'Nep.101', 'Compulsory Nepali', 'नेपाली', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Eng.102', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mth.103', 'Compulsory Mathematics', 'गणित', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Sci.104', 'Science & Technology', 'विज्ञान तथा प्रविधि', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.105', 'Social Studies & Human Values', 'सामाजिक अध्ययन तथा मानव मूल्य', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Opt.106', 'Optional I (Economics)', 'ऐच्छिक प्रथम (अर्थशास्त्र)', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
            (cid, 'Opt.107', 'Optional II (Computer Science)', 'ऐच्छिक द्वितीय (कम्प्युटर विज्ञान)', 4.0, 50.0, 18.0, 50.0, 20.0, 1),
        ])

    # Class 11 Science (NEB)
    if 'Class 11 Science' in class_map:
        cid = class_map['Class 11 Science']
        all_subjects.extend([
            (cid, 'Com.Eng.001', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.002', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Phy.101', 'Physics', 'भौतिक विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Che.102', 'Chemistry', 'रसायन विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mat.103', 'Mathematics', 'गणित', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Bio.104', 'Biology', 'जीव विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
            (cid, 'Opt.Com.105', 'Computer Science', 'कम्प्युटर विज्ञान', 4.0, 50.0, 18.0, 50.0, 20.0, 1),
        ])

    # Class 12 Science (NEB)
    if 'Class 12 Science' in class_map:
        cid = class_map['Class 12 Science']
        all_subjects.extend([
            (cid, 'Com.Eng.002', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.001', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Phy.201', 'Physics', 'भौतिक विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Che.202', 'Chemistry', 'रसायन विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mat.203', 'Mathematics', 'गणित', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Bio.204', 'Biology', 'जीव विज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
            (cid, 'Opt.Com.205', 'Computer Science', 'कम्प्युटर विज्ञान', 4.0, 50.0, 18.0, 50.0, 20.0, 1),
        ])

    # Class 11 Management (NEB)
    if 'Class 11 Management' in class_map:
        cid = class_map['Class 11 Management']
        all_subjects.extend([
            (cid, 'Com.Eng.001', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.002', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.101', 'Social Studies & Life Skills', 'सामाजिक अध्ययन तथा जीवनोपयोगी शिक्षा', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Acc.101', 'Principles of Accounting I', 'लेखाविधि सिद्धान्त १', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Eco.102', 'Economics I', 'अर्थशास्त्र १', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'BSt.103', 'Business Studies', 'व्यवसाय अध्ययन', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Opt.Bmt.104', 'Business Mathematics / Computer', 'व्यावसायिक गणित / कम्प्युटर', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
        ])

    # Class 12 Management (NEB)
    if 'Class 12 Management' in class_map:
        cid = class_map['Class 12 Management']
        all_subjects.extend([
            (cid, 'Com.Eng.002', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.001', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.201', 'Social Studies & Life Skills', 'सामाजिक अध्ययन तथा जीवनोपयोगी शिक्षा', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Acc.201', 'Principles of Accounting II', 'लेखाविधि सिद्धान्त २', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Eco.202', 'Economics II', 'अर्थशास्त्र २', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Mkt.203', 'Marketing / Business Studies', 'बजारीकरण', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Opt.Bmt.204', 'Business Mathematics / Computer', 'व्यावसायिक गणित / कम्प्युटर', 4.0, 75.0, 27.0, 25.0, 10.0, 1),
        ])

    # Class 11 Education (NEB)
    if 'Class 11 Education' in class_map:
        cid = class_map['Class 11 Education']
        all_subjects.extend([
            (cid, 'Com.Eng.001', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.002', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.101', 'Social Studies & Life Skills', 'सामाजिक अध्ययन तथा जीवनोपयोगी शिक्षा', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.101', 'Philosophical Foundations of Education', 'शिक्षाको दार्शनिक आधार', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.102', 'Child Development & Learning', 'बालविकास तथा सिकाइ', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.103', 'Instructional Pedagogy & Teaching Practice', 'शिक्षण विधि तथा अभ्यास', 4.0, 50.0, 18.0, 50.0, 20.0, 0),
        ])

    # Class 12 Education (NEB)
    if 'Class 12 Education' in class_map:
        cid = class_map['Class 12 Education']
        all_subjects.extend([
            (cid, 'Com.Eng.002', 'Compulsory English', 'अंग्रेजी', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Com.Nep.001', 'Compulsory Nepali', 'नेपाली', 3.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Soc.201', 'Social Studies & Life Skills', 'सामाजिक अध्ययन तथा जीवनोपयोगी शिक्षा', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.201', 'Curriculum & Evaluation', 'पाठ्यक्रम तथा मूल्याङ्कन', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.202', 'Educational Psychology', 'शिक्षा मनोविज्ञान', 4.0, 75.0, 27.0, 25.0, 10.0, 0),
            (cid, 'Edu.203', 'Practicum & School Internship', 'विद्यालय शिक्षण अभ्यास', 4.0, 30.0, 11.0, 70.0, 28.0, 0),
        ])

    cur.execute("DELETE FROM subjects;")
    cur.executemany("""
    INSERT INTO subjects (
        class_id, code, name_en, name_np, credit_hours,
        theory_full_marks, theory_pass_marks, practical_full_marks, practical_pass_marks, is_optional
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, all_subjects)

    # 5. Examination Terms
    cur.execute("DELETE FROM exams;")
    exams_data = [
        ('First Terminal Examination 2081', 'First Term', '2081', '2081-04-15', '2081-04-24', 1),
        ('Second Terminal Examination 2081', 'Second Term', '2081', '2081-08-20', '2081-08-30', 1),
        ('Pre-SEE Model Examination 2081', 'Pre-Board', '2081', '2081-11-10', '2081-11-20', 1),
        ('Annual Examination 2081', 'Final', '2081', '2081-12-05', '2081-12-16', 1),
    ]
    cur.executemany("""
    INSERT INTO exams (name, term, academic_year, start_date, end_date, is_published)
    VALUES (?, ?, ?, ?, ?, ?);
    """, exams_data)

    cur.execute("SELECT id, name FROM exams;")
    exam_map = {row['name']: row['id'] for row in cur.fetchall()}

    # 6. Students
    sec_10_a = section_map[f"{c10_id}_A"]
    sec_10_b = section_map[f"{c10_id}_B"]
    sec_11_sci = section_map[f"{c11_sci_id}_A"]
    sec_11_mgmt = section_map[f"{c11_mgmt_id}_A"]
    sec_9_a = section_map[f"{c9_id}_A"]
    sec_8_a = section_map[f"{c8_id}_A"]

    students_data = [
        # Class 10 Students (For SEE Grade Sheet showcase)
        ('SSS-2081-1001', 1, 'Aayush', 'Adhikari', 'आयुष अधिकारी', 'Male', '2065-03-12', '2008-06-26', c10_id, sec_10_a, 'Hari Prasad Adhikari', 'Father', '9842100001', 'Bhadrapur-2, Jhapa', 'A+', '2075-01-15', 'Active'),
        ('SSS-2081-1002', 2, 'Bina', 'Shrestha', 'बिना श्रेष्ठ', 'Female', '2065-05-20', '2008-09-05', c10_id, sec_10_a, 'Gopal Shrestha', 'Father', '9842100002', 'Bhadrapur-2, Sagarmatha', 'B+', '2075-01-15', 'Active'),
        ('SSS-2081-1003', 3, 'Chandan', 'Yadav', 'चन्दन यादव', 'Male', '2064-11-14', '2008-02-27', c10_id, sec_10_a, 'Ram Kumar Yadav', 'Father', '9842100003', 'Bhadrapur-3, Jhapa', 'O+', '2076-01-10', 'Active'),
        ('SSS-2081-1004', 4, 'Dikshya', 'Rai', 'दीक्षा राई', 'Female', '2065-08-05', '2008-11-20', c10_id, sec_10_a, 'Bir Bahadur Rai', 'Father', '9842100004', 'Bhadrapur-2, Jhapa', 'AB+', '2074-01-12', 'Active'),
        ('SSS-2081-1005', 5, 'Kiran', 'Khadka', 'किरण खड्का', 'Male', '2065-02-18', '2008-06-01', c10_id, sec_10_a, 'Dhan Bahadur Khadka', 'Father', '9842100005', 'Bhadrapur-1, Jhapa', 'A-', '2075-01-15', 'Active'),
        ('SSS-2081-1006', 6, 'Pooja', 'Dahal', 'पूजा दाहाल', 'Female', '2065-07-25', '2008-11-10', c10_id, sec_10_a, 'Keshav Dahal', 'Father', '9842100006', 'Bhadrapur-2, Sagarmatha', 'O+', '2075-01-18', 'Active'),
        ('SSS-2081-1007', 7, 'Roshan', 'Giri', 'रोशन गिरी', 'Male', '2064-12-10', '2008-03-24', c10_id, sec_10_b, 'Krishna Giri', 'Father', '9842100007', 'Bhadrapur-2, Jhapa', 'B-', '2077-01-12', 'Active'),
        ('SSS-2081-1008', 8, 'Sita', 'Tamang', 'सीता तामाङ', 'Female', '2065-04-14', '2008-07-29', c10_id, sec_10_b, 'Pasang Tamang', 'Father', '9842100008', 'Bhadrapur-4, Jhapa', 'B+', '2075-01-15', 'Active'),
        
        # Class 11 Science Students
        ('SSS-2081-1101', 1, 'Bibek', 'Karki', 'विवेक कार्की', 'Male', '2064-01-10', '2007-04-23', c11_sci_id, sec_11_sci, 'Ganesh Karki', 'Father', '9842100010', 'Bhadrapur-2, Jhapa', 'O+', '2081-03-20', 'Active'),
        ('SSS-2081-1102', 2, 'Anjali', 'Sharma', 'अञ्जली शर्मा', 'Female', '2064-06-15', '2007-09-30', c11_sci_id, sec_11_sci, 'Madhav Sharma', 'Father', '9842100011', 'Bhadrapur-3, Jhapa', 'A+', '2081-03-22', 'Active'),
        
        # Class 11 Management Students
        ('SSS-2081-1121', 1, 'Saurav', 'Thapa', 'सौरभ थापा', 'Male', '2064-09-02', '2007-12-17', c11_mgmt_id, sec_11_mgmt, 'Bhim Thapa', 'Father', '9842100020', 'Bhadrapur-2, Jhapa', 'B+', '2081-03-25', 'Active'),
        ('SSS-2081-1122', 2, 'Nisha', 'Chaudhary', 'निशा चौधरी', 'Female', '2064-04-18', '2007-08-03', c11_mgmt_id, sec_11_mgmt, 'Sanjay Chaudhary', 'Father', '9842100021', 'Bhadrapur-1, Jhapa', 'O+', '2081-03-25', 'Active'),

        # Class 9 Student
        ('SSS-2081-0901', 1, 'Pradeep', 'Bhandari', 'प्रदीप भण्डारी', 'Male', '2066-02-14', '2009-05-28', c9_id, sec_9_a, 'Khim Bhandari', 'Father', '9842100030', 'Bhadrapur-2, Jhapa', 'A+', '2078-01-10', 'Active'),
        # Class 8 Student
        ('SSS-2081-0801', 1, 'Swastika', 'Nepal', 'स्वस्तिका नेपाल', 'Female', '2067-08-11', '2010-11-27', c8_id, sec_8_a, 'Balaram Nepal', 'Father', '9842100040', 'Bhadrapur-2, Jhapa', 'B+', '2079-01-10', 'Active'),
    ]

    cur.execute("DELETE FROM students;")
    cur.executemany("""
    INSERT INTO students (
        reg_no, roll_no, first_name, last_name, name_np,
        gender, dob_bs, dob_ad, class_id, section_id,
        guardian_name, guardian_relation, guardian_phone, address,
        blood_group, admission_date, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, students_data)

    cur.execute("SELECT id, reg_no, first_name, last_name FROM students;")
    student_map = {row['reg_no']: row['id'] for row in cur.fetchall()}

    # 7. Seed Marks for Class 10 Students in "Second Terminal Examination 2081"
    cur.execute("DELETE FROM marks;")
    exam_term2_id = exam_map['Second Terminal Examination 2081']

    cur.execute("SELECT id, code, credit_hours, theory_full_marks, practical_full_marks FROM subjects WHERE class_id = ?;", (c10_id,))
    c10_sub_list = cur.fetchall()

    # Scores sample matrix:
    # Aayush: Top student (A+ / A)
    # Bina: High achiever (A / B+)
    # Chandan: Good (B+ / B)
    # Dikshya: Satisfactory (B / C+)
    # Kiran: Edge case / Borderline pass
    # Pooja: One subject NG test case to verify CDC 2078/2080 NG enforcement!
    score_presets = {
        'SSS-2081-1001': { # Aayush
            'Nep.101': (68.0, 24.0),
            'Eng.102': (70.0, 24.5),
            'Mth.103': (73.0, 25.0),
            'Sci.104': (69.0, 24.0),
            'Soc.105': (67.0, 23.5),
            'Opt.106': (71.0, 24.0),
            'Opt.107': (48.0, 48.0) # 50 th, 50 pr
        },
        'SSS-2081-1002': { # Bina
            'Nep.101': (62.0, 23.0),
            'Eng.102': (65.0, 24.0),
            'Mth.103': (66.0, 24.0),
            'Sci.104': (64.0, 23.0),
            'Soc.105': (63.0, 22.0),
            'Opt.106': (65.0, 23.0),
            'Opt.107': (44.0, 46.0)
        },
        'SSS-2081-1003': { # Chandan
            'Nep.101': (54.0, 21.0),
            'Eng.102': (52.0, 20.0),
            'Mth.103': (58.0, 22.0),
            'Sci.104': (55.0, 21.0),
            'Soc.105': (53.0, 20.0),
            'Opt.106': (56.0, 21.0),
            'Opt.107': (38.0, 42.0)
        },
        'SSS-2081-1004': { # Dikshya
            'Nep.101': (46.0, 20.0),
            'Eng.102': (48.0, 19.0),
            'Mth.103': (44.0, 18.0),
            'Sci.104': (45.0, 19.0),
            'Soc.105': (49.0, 20.0),
            'Opt.106': (47.0, 19.0),
            'Opt.107': (32.0, 38.0)
        },
        'SSS-2081-1005': { # Kiran
            'Nep.101': (36.0, 18.0),
            'Eng.102': (38.0, 17.0),
            'Mth.103': (35.0, 16.0),
            'Sci.104': (37.0, 17.0),
            'Soc.105': (39.0, 18.0),
            'Opt.106': (36.0, 17.0),
            'Opt.107': (22.0, 32.0)
        },
        'SSS-2081-1006': { # Pooja - NG case (theory mark 22 in Math, below pass mark 27/35%)
            'Nep.101': (55.0, 21.0),
            'Eng.102': (58.0, 22.0),
            'Mth.103': (22.0, 18.0), # Below 27/75 (29.3%) -> CDC NG!
            'Sci.104': (54.0, 20.0),
            'Soc.105': (57.0, 21.0),
            'Opt.106': (52.0, 20.0),
            'Opt.107': (36.0, 40.0)
        },
        'SSS-2081-1007': { # Roshan
            'Nep.101': (60.0, 22.0),
            'Eng.102': (61.0, 22.0),
            'Mth.103': (63.0, 23.0),
            'Sci.104': (59.0, 21.0),
            'Soc.105': (62.0, 22.0),
            'Opt.106': (61.0, 22.0),
            'Opt.107': (40.0, 44.0)
        },
        'SSS-2081-1008': { # Sita
            'Nep.101': (66.0, 23.0),
            'Eng.102': (68.0, 24.0),
            'Mth.103': (70.0, 24.0),
            'Sci.104': (67.0, 23.0),
            'Soc.105': (65.0, 23.0),
            'Opt.106': (68.0, 24.0),
            'Opt.107': (45.0, 47.0)
        }
    }

    marks_data = []
    for reg_no, sub_marks in score_presets.items():
        sid = student_map.get(reg_no)
        if not sid:
            continue
        for sub_row in c10_sub_list:
            code = sub_row['code']
            if code in sub_marks:
                th, pr = sub_marks[code]
                marks_data.append((exam_term2_id, sid, sub_row['id'], th, pr))

    cur.executemany("""
    INSERT INTO marks (exam_id, student_id, subject_id, theory_obtained, practical_obtained)
    VALUES (?, ?, ?, ?, ?);
    """, marks_data)

    # 8. Fee Heads & Structures
    cur.execute("DELETE FROM fee_heads;")
    fee_heads = [
        ('Monthly Tuition Fee', 1),
        ('Annual Admission / Registration Fee', 0),
        ('Terminal Examination Fee', 1),
        ('Computer & ICT Lab Fee', 1),
        ('Science Practical Lab Fee', 1),
        ('Midday Meal / दिवा खाजा Support', 1),
        ('Identity Card & Library Fee', 0),
        ('Sports & Extracurricular Fee', 1),
    ]
    cur.executemany("INSERT INTO fee_heads (name, is_recurring) VALUES (?, ?);", fee_heads)

    cur.execute("SELECT id, name FROM fee_heads;")
    fh_map = {row['name']: row['id'] for row in cur.fetchall()}

    # Set up fee structures for Class 10
    fee_structures = [
        (c10_id, fh_map['Monthly Tuition Fee'], 1200.0),
        (c10_id, fh_map['Terminal Examination Fee'], 400.0),
        (c10_id, fh_map['Computer & ICT Lab Fee'], 300.0),
        (c10_id, fh_map['Science Practical Lab Fee'], 300.0),
        (c10_id, fh_map['Sports & Extracurricular Fee'], 150.0),
        (c10_id, fh_map['Identity Card & Library Fee'], 250.0),
        # Class 11 Science
        (c11_sci_id, fh_map['Monthly Tuition Fee'], 2500.0),
        (c11_sci_id, fh_map['Science Practical Lab Fee'], 800.0),
        (c11_sci_id, fh_map['Computer & ICT Lab Fee'], 500.0),
        (c11_sci_id, fh_map['Terminal Examination Fee'], 600.0),
        # Class 11 Management
        (c11_mgmt_id, fh_map['Monthly Tuition Fee'], 1800.0),
        (c11_mgmt_id, fh_map['Computer & ICT Lab Fee'], 400.0),
        (c11_mgmt_id, fh_map['Terminal Examination Fee'], 500.0),
    ]
    cur.execute("DELETE FROM fee_structures;")
    cur.executemany("""
    INSERT INTO fee_structures (class_id, fee_head_id, amount)
    VALUES (?, ?, ?);
    """, fee_structures)

    # 9. Invoices & Payments for Demonstration
    cur.execute("DELETE FROM invoices;")
    cur.execute("DELETE FROM invoice_items;")
    cur.execute("DELETE FROM payments;")

    sample_invoices = [
        ('INV-2081-1001', student_map['SSS-2081-1001'], 'Shrawan', '2081', 2350.0, 150.0, 0.0, 2200.0, 'Paid', '2081-04-05'),
        ('INV-2081-1002', student_map['SSS-2081-1002'], 'Shrawan', '2081', 2350.0, 0.0, 0.0, 2350.0, 'Paid', '2081-04-06'),
        ('INV-2081-1003', student_map['SSS-2081-1003'], 'Shrawan', '2081', 2350.0, 0.0, 0.0, 1500.0, 'Partially Paid', '2081-04-07'),
        ('INV-2081-1004', student_map['SSS-2081-1004'], 'Shrawan', '2081', 2350.0, 0.0, 0.0, 0.0, 'Unpaid', '2081-04-07'),
        ('INV-2081-1005', student_map['SSS-2081-1005'], 'Bhadra', '2081', 2350.0, 350.0, 0.0, 2000.0, 'Paid', '2081-05-08'),
        ('INV-2081-1006', student_map['SSS-2081-1101'], 'Shrawan', '2081', 4400.0, 0.0, 0.0, 4400.0, 'Paid', '2081-04-10'),
    ]

    for inv_no, st_id, month, year, total, disc, fine, paid, status, created_at in sample_invoices:
        cur.execute("""
        INSERT INTO invoices (invoice_no, student_id, month, year, total_amount, discount, fine, paid_amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (inv_no, st_id, month, year, total, disc, fine, paid, status, created_at))
        inv_id = cur.lastrowid

        # Insert items
        items = [
            (inv_id, 'Monthly Tuition Fee', 1200.0 if total < 4000 else 2500.0),
            (inv_id, 'Terminal Examination Fee', 400.0 if total < 4000 else 600.0),
            (inv_id, 'Computer & ICT Lab Fee', 300.0 if total < 4000 else 500.0),
            (inv_id, 'Science Practical Lab Fee', 300.0 if total < 4000 else 800.0),
            (inv_id, 'Sports & Extracurricular Fee', 150.0),
        ]
        cur.executemany("INSERT INTO invoice_items (invoice_id, fee_head_name, amount) VALUES (?, ?, ?);", items)

        # If paid, generate payment receipt
        if paid > 0:
            rec_no = f"REC-{inv_no.replace('INV-', '')}"
            cur.execute("""
            INSERT INTO payments (receipt_no, invoice_id, student_id, amount_paid, payment_mode, transaction_ref, payment_date, received_by, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (rec_no, inv_id, st_id, paid, 'Cash' if st_id % 2 == 1 else 'Fonepay/eSewa', 'FP98234190' if st_id % 2 == 0 else 'CASH-CT', created_at, 'Manoj Shrestha (Accountant)', 'Monthly fee settled with receipt issued.'))

    # 10. School Expenses
    cur.execute("DELETE FROM expenses;")
    expenses_data = [
        ('Midday Meal (दिवा खाजा) Provisions - Local Farmers Group', 'Midday Meal / दिवा खाजा', 42500.0, 'Fonepay/eSewa', '2081-05-02', 'Bhadrapur Agro Coop', 'Principal', 'Nutritious lunch supplies for primary students'),
        ('Laboratory Chemicals & Glassware - Science Lab', 'Science Lab Supplies', 28400.0, 'Bank Deposit', '2081-04-18', 'Koshi Scientific Suppliers, Biratnagar', 'Exam Coordinator', 'Physics & Chemistry lab practical kits'),
        ('High-Speed Fiber Internet Bill - 6 Months', 'Utilities', 15500.0, 'Bank Deposit', '2081-04-10', 'WorldLink Communications', 'ICT Head', 'School ICT Lab and Admin Network'),
        ('Stationery & Examination Printing Paper (Rim)', 'Stationery', 19800.0, 'Cash', '2081-04-20', 'Jhapa Pustak Bhandar', 'Accountant', 'Terminal exam question paper & marksheet print stock'),
        ('Classroom Bench Repair & Painting', 'Maintenance', 16000.0, 'Cash', '2081-05-15', 'Local Wood Crafts Bhadrapur', 'Principal', 'Renovation of Block B classrooms'),
        ('District Inter-School Volleyball & Athletic Gear', 'Sports & Events', 12500.0, 'Fonepay/eSewa', '2081-05-22', 'Everest Sports Center', 'Sports Incharge', 'Jerseys and volleyball equipment'),
    ]
    cur.executemany("""
    INSERT INTO expenses (title, category, amount, payment_mode, expense_date, paid_to, approved_by, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, expenses_data)

    # 11. Staff / Teachers
    cur.execute("DELETE FROM staff;")
    staff_data = [
        ('EMP-001', 'Ram Prasad Adhikari', 'रामप्रसाद अधिकारी', 'Principal / Headmaster', 'Administration', 'M.Ed (Educational Administration)', '9852601001', 'principal@sagarmathaschool.edu.np', '2058-04-01', 'Active'),
        ('EMP-002', 'Sharada Nepal', 'शारदा नेपाल', 'Vice Principal & English Dept Head', 'Languages', 'M.A., B.Ed (English)', '9852601002', 'sharada.nepal@sagarmathaschool.edu.np', '2064-02-15', 'Active'),
        ('EMP-003', 'Dr. Janak Raj Bhattarai', 'डा. जनकराज भट्टराई', 'Secondary Science & Tech Coordinator', 'Science', 'M.Sc., Ph.D (Physics)', '9842601003', 'janak.sci@sagarmathaschool.edu.np', '2068-05-10', 'Active'),
        ('EMP-004', 'Manoj Kumar Shrestha', 'मनोज कुमार श्रेष्ठ', 'Senior Accountant & Bursar', 'Administration', 'M.B.S (Finance)', '9842601004', 'accounts@sagarmathaschool.edu.np', '2070-08-01', 'Active'),
        ('EMP-005', 'Surendra Nath Sah', 'सुरेन्द्र नाथ साह', 'Senior Mathematics Specialist', 'Mathematics', 'M.Sc. (Mathematics)', '9842601005', 'surendra.math@sagarmathaschool.edu.np', '2066-03-20', 'Active'),
        ('EMP-006', 'Devendra Chaudhary', 'देवेन्द्र चौधरी', 'ICT Coordinator & Computer Teacher', 'ICT', 'B.Sc. CSIT, MCA', '9842601006', 'dev.ict@sagarmathaschool.edu.np', '2075-01-15', 'Active'),
        ('EMP-007', 'Gita Devi Pokhrel', 'गीता देवी पोखरेल', 'Senior Nepali Literature Teacher', 'Languages', 'M.A. (Nepali), B.Ed', '9842601007', 'gita.nep@sagarmathaschool.edu.np', '2065-07-12', 'Active'),
        ('EMP-008', 'Bikram Limbu', 'विक्रम लिम्बु', 'Social Studies & Moral Education', 'Social Studies', 'M.A. (History), B.Ed', '9842601008', 'bikram.soc@sagarmathaschool.edu.np', '2072-04-18', 'Active'),
        ('EMP-009', 'Saraswati Karki', 'सरस्वती कार्की', 'Early Childhood (ECD) Lead Facilitator', 'Primary', 'B.Ed (Child Development)', '9842601009', 'ecd@sagarmathaschool.edu.np', '2073-02-10', 'Active'),
        ('EMP-010', 'Nabin Basnet', 'नवीन बस्नेत', 'Sports & Physical Education Instructor', 'Extracurricular', 'B.P.Ed', '9842601010', 'sports@sagarmathaschool.edu.np', '2076-06-01', 'Active'),
    ]
    cur.executemany("""
    INSERT INTO staff (emp_code, name_en, name_np, role, department, qualification, phone, email, joining_date, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, staff_data)

    # 12. Public Notices
    cur.execute("DELETE FROM notices;")
    notices_data = [
        ('SEE Model Examination 2081 Routine Published', 'Exam', 'All Grade 10 students are informed that the Pre-SEE Model Examination will commence from Falgun 10, 2081. Detailed subject routines and admit cards can be obtained from the examination department.', '2081-05-10', 1, 'Routine_Model_Exam_2081.pdf'),
        ('Admission Open for Class 11 (Science, Management, Education) - Academic Session 2081/82', 'Admission', 'Shree Sagarmatha Secondary School announces open admissions for Grade 11. Meritorious and underprivileged community students will be awarded full and partial scholarships by Bhadrapur Municipality and School SMC.', '2081-03-20', 1, 'Class11_Prospectus_2081.pdf'),
        ('Midday Meal (दिवा खाजा) Quality & Hygiene Inspection Completed', 'General', 'The School Management Committee (SMC) along with Ward-2 health representatives successfully conducted the quarterly hygiene review for the ECD to Grade 5 Midday Meal program. Safe and fresh organic menu finalized.', '2081-05-02', 0, None),
        ('Annual Sports & Cultural Week 2081 Announcement', 'Academic', 'Annual sports meet including Volleyball, Football, Badminton, Quiz, and Traditional Folk Dance competitions will take place on Mangsir 20-25.', '2081-04-28', 0, 'Sports_Week_Guidelines.pdf'),
        ('Parent-Teacher Association (PTA) General Meeting Notice', 'General', 'The PTA meeting for Classes 8, 9, 10, and 12 will be held this Saturday at 11:00 AM in the School Multi-Purpose Hall to discuss second terminal academic progress.', '2081-05-18', 0, None),
    ]
    cur.executemany("""
    INSERT INTO notices (title, category, content, posted_date, is_pinned, file_attachment)
    VALUES (?, ?, ?, ?, ?, ?);
    """, notices_data)

    # 13. Online Admission Inquiries
    cur.execute("DELETE FROM admission_inquiries;")
    inquiries_data = [
        ('Sandesh Gautam', 'Class 11 Science', 'Bishnu Gautam', '9842998877', 'sandesh.g@gmail.com', 'Bhadrapur-3, Jhapa', 'Saraswati Secondary School, Mechinagar', 'Interested in Computer Science & Physics track. Seeking scholarship criteria details.', 'Pending'),
        ('Prerana Adhikari', 'Class 1', 'Madhav Adhikari', '9812345678', 'madhav.adh@yahoo.com', 'Bhadrapur-2, Sagarmatha', 'Little Flowers Nursery', 'Admitting for Grade 1 under English medium section.', 'Contacted'),
        ('Rohan Baral', 'Class 11 Management', 'Sita Baral', '9806123456', 'rohan.baral@gmail.com', 'Bhadrapur-5, Chandragadhi', 'Bhadrapur Secondary School', 'Opting for Accountancy and Computer Science stream.', 'Pending'),
    ]
    cur.executemany("""
    INSERT INTO admission_inquiries (applicant_name, applying_class, guardian_name, phone, email, address, previous_school, message, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, inquiries_data)

    # 14. Daily Attendance Samples
    cur.execute("DELETE FROM attendance;")
    att_samples = [
        (student_map['SSS-2081-1001'], '2081-05-20', 'Present', ''),
        (student_map['SSS-2081-1002'], '2081-05-20', 'Present', ''),
        (student_map['SSS-2081-1003'], '2081-05-20', 'Present', ''),
        (student_map['SSS-2081-1004'], '2081-05-20', 'Absent', 'Family function'),
        (student_map['SSS-2081-1005'], '2081-05-20', 'Present', ''),
        (student_map['SSS-2081-1006'], '2081-05-20', 'Present', ''),
        (student_map['SSS-2081-1007'], '2081-05-20', 'Leave', 'Medical checkup'),
        (student_map['SSS-2081-1008'], '2081-05-20', 'Present', ''),
    ]
    cur.executemany("""
    INSERT INTO attendance (student_id, attendance_date, status, remarks)
    VALUES (?, ?, ?, ?);
    """, att_samples)

    # 15. User Accounts for Multi-Tier RBAC
    from database import hash_password
    cur.execute("DELETE FROM users;")
    cur.execute("DELETE FROM sessions;")

    users_seed = [
        ('admin', 'admin123', 'Ram Prasad Adhikari (Principal)', 'admin', None, 1),
        ('teacher', 'teacher123', 'Dr. Janak Raj Bhattarai (Exam Coordinator)', 'teacher', None, 3),
        ('accountant', 'account123', 'Manoj Kumar Shrestha (Senior Bursar)', 'accountant', None, 4),
        ('student10', 'student123', 'Aayush Adhikari (Student Class 10)', 'student', student_map['SSS-2081-1001'], None),
        ('student_ng', 'student123', 'Pooja Dahal (Student Class 10)', 'student', student_map['SSS-2081-1006'], None),
    ]

    for uname, pwd, fname, role, st_id, staff_id in users_seed:
        pwd_hash, salt = hash_password(pwd)
        cur.execute("""
        INSERT INTO users (username, password_hash, salt, full_name, role, linked_student_id, linked_staff_id, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Active');
        """, (uname, pwd_hash, salt, fname, role, st_id, staff_id))

    # 16. School Photo Gallery
    cur.execute("DELETE FROM gallery_photos;")
    
    def make_svg_photo(bg1, bg2, icon, title, subtitle):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 500" width="100%" height="100%">
          <defs>
            <linearGradient id="grad_{icon}" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stop-color="{bg1}" />
              <stop offset="100%" stop-color="{bg2}" />
            </linearGradient>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
            </pattern>
          </defs>
          <rect width="800" height="500" fill="url(#grad_{icon})" />
          <rect width="800" height="500" fill="url(#grid)" />
          <circle cx="400" cy="200" r="100" fill="rgba(255,255,255,0.12)" />
          <text x="400" y="235" font-size="80" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif">{icon}</text>
          <rect x="40" y="340" width="720" height="115" rx="16" fill="rgba(15,23,42,0.7)" />
          <text x="400" y="380" font-size="22" font-weight="bold" fill="#ffffff" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif">{title}</text>
          <text x="400" y="420" font-size="15" fill="#93c5fd" text-anchor="middle" font-family="system-ui, -apple-system, sans-serif">{subtitle}</text>
        </svg>'''
        import urllib.parse
        return f"data:image/svg+xml;utf8,{urllib.parse.quote(svg)}"

    gallery_photos = [
        (
            'Main Academic Complex & Green Lawns',
            'मुख्य शैक्षिक भवन तथा सभा प्राङ्गण',
            'Campus',
            make_svg_photo('#0f172a', '#1e3a8a', '🏫', 'Main Academic Complex & Central Assembly Grounds', 'Shree Sagarmatha Secondary School • Bhadrapur 2, Jhapa'),
            'Three-storied earthquake-resilient school complex with spacious corridors and greenery.',
            'भूकम्प प्रतिरोधी तीन तले आधुनिक शैक्षिक भवन तथा फराकिलो प्रार्थना मैदान ।',
            1, 1
        ),
        (
            'Modern Science Practical Laboratory',
            'उच्चस्तरीय भौतिक तथा रसायन विज्ञान प्रयोगशाला',
            'Academic',
            make_svg_photo('#064e3b', '#0f766e', '🔬', 'Modern Science Practical Laboratory', 'Physics, Chemistry & Biology Research Station'),
            'Hands-on experimental setup equipped for secondary and +2 science streams.',
            'माध्यमिक तथा कक्षा ११-१२ विज्ञान संकायका लागि आधुनिक उपकरणसहितको प्रयोगशाला ।',
            1, 2
        ),
        (
            'ICT Digital Computer Lab',
            'सूचना प्रविधि तथा डिजिटल कम्प्युटर प्रयोगशाला',
            'Academic',
            make_svg_photo('#1e1b4b', '#4338ca', '💻', 'ICT Digital Computer Lab & Smart Learning', '40+ Connected Workstations with High-Speed Internet'),
            'Modern computer laboratory providing digital literacy from primary to Grade 12.',
            'इन्टरनेट सुविधा र ४०+ कम्प्युटरसहितको अत्याधुनिक सूचना प्रविधि प्रयोगशाला ।',
            1, 3
        ),
        (
            'Annual Inter-House Football Cup',
            'वार्षिक अन्तर-सदन फुटबल प्रतियोगिता २०८१',
            'Sports',
            make_svg_photo('#14532d', '#15803d', '⚽', 'Annual Inter-House Football Championship 2081', 'Sagarmatha Sports Arena • Bhadrapur 2'),
            'Energetic inter-house football tournament fostering team spirit and fitness.',
            'विद्यार्थीहरूको शारीरिक तन्दुरुस्ती र खेल भावना प्रवर्द्धन गर्ने अन्तर-सदन फुटबल प्रतियोगिता ।',
            1, 4
        ),
        (
            'Saraswati Puja & Cultural Celebration',
            'श्रीपञ्चमी तथा सरस्वती पूजा सांस्कृतिक उत्सव',
            'Events',
            make_svg_photo('#701a75', '#a21caf', '🪕', 'Saraswati Puja & Cultural Celebration', 'Vidyarambha, Classical Music & Folk Dance Showcase'),
            'Annual worshipping of Goddess Saraswati with traditional music, poetry and art.',
            'विद्याकी देवी सरस्वतीको पूजा-आराधना तथा विद्यार्थीहरूद्वारा प्रस्तुत विविध सांस्कृतिक कार्यक्रम ।',
            1, 5
        ),
        (
            'Central Library & Quiet Reading Hall',
            'पुस्तकालय तथा अनुसन्धान अध्ययन कक्ष',
            'Academic',
            make_svg_photo('#312e81', '#1e3a8a', '📚', 'Central Library & Reading Hall', 'Over 6,500 Books, Reference Journals & Daily Periodicals'),
            'Rich repository of curriculum books, literature, encyclopedia and newspapers.',
            'पाठ्यपुस्तक, साहित्य, ज्ञानकोष र सन्दर्भ सामग्रीहरूले भरिपूर्ण विद्यालय पुस्तकालय ।',
            0, 6
        ),
        (
            'Athletics & Track Field Meet',
            'वार्षिक एथलेटिक्स तथा दौड प्रतियोगिता',
            'Sports',
            make_svg_photo('#7c2d12', '#c2410c', '🏃', 'Annual Track & Field Athletics Meet', '100m Sprint, Long Jump & Relay Race Events'),
            'Students competing in athletic sprint, hurdles, high jump, and relay.',
            '१०० मिटर दौड, लङ जम्प, रिले तथा विविध ट्र्याक एन्ड फिल्ड प्रतिस्पर्धा ।',
            0, 7
        ),
        (
            '47th Annual School Day & Prize Distribution',
            '४७ औँ वार्षिक उत्सव तथा पुरस्कार वितरण समारोह',
            'Events',
            make_svg_photo('#831843', '#be185d', '🏆', '47th Annual School Day & Award Ceremony', 'Honoring Academic & Extracurricular Excellence'),
            'Celebrating 47 glorious years of community education with dignity and awards.',
            'शैक्षिक तथा अतिरिक्त क्रियाकलापमा उत्कृष्ट विद्यार्थीहरूलाई सम्मान तथा पुरस्कार वितरण ।',
            1, 8
        ),
        (
            'Early Childhood (ECD) Activity Corner',
            'प्रारम्भिक बाल विकास (ECD) क्रियाकलाप केन्द्र',
            'Academic',
            make_svg_photo('#713f12', '#b45309', '🎨', 'Early Childhood Development (ECD) Corner', 'Play-based Learning, Montessori Toys & Story Sessions'),
            'Colorful, safe, and engaging environment for toddlers and nursery learners.',
            'बालबालिकाहरूको उमेर अनुसार खेल, चित्रकला र मनोरञ्जनात्मक सिकाइ वातावरण ।',
            0, 9
        ),
        (
            'Centenary Botanical Garden & Tree Plantation',
            'विद्यालय हरियाली बगैँचा तथा वृक्षारोपण अभियान',
            'Campus',
            make_svg_photo('#064e3b', '#047857', '🌱', 'Campus Green Belt & Environmental Initiative', 'Student Eco Club Tree Plantation Drive'),
            'Lush green campus trees planted and nurtured by Eco Club student volunteers.',
            'इको क्लबका विद्यार्थीहरूद्वारा सञ्चालित वातावरण संरक्षण तथा वृक्षारोपण अभियान ।',
            0, 10
        ),
    ]

    cur.executemany("""
    INSERT INTO gallery_photos (title, title_np, category, image_url, caption, caption_np, featured, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, gallery_photos)

    conn.commit()
    conn.close()
    print("Seeding completed successfully with realistic data and RBAC accounts for Shree Sagarmatha Secondary School.")

if __name__ == "__main__":
    seed_database()
