"""
test_app.py - Automated Verification Test Suite for Sagarmatha EMS & CDC Grading Engine
"""

import unittest
import sqlite3
import json
import os
from database import get_db_connection, calculate_grade_and_gp, calculate_subject_evaluation

class TestNepalCDCGrading(unittest.TestCase):
    
    def test_grade_boundaries(self):
        # 90+ -> A+
        self.assertEqual(calculate_grade_and_gp(95.0)[0], "A+")
        self.assertEqual(calculate_grade_and_gp(90.0)[0], "A+")
        self.assertEqual(calculate_grade_and_gp(90.0)[1], 4.0)

        # 80-89.9 -> A
        self.assertEqual(calculate_grade_and_gp(85.0)[0], "A")
        self.assertEqual(calculate_grade_and_gp(80.0)[1], 3.6)

        # 70-79.9 -> B+
        self.assertEqual(calculate_grade_and_gp(72.5)[0], "B+")
        self.assertEqual(calculate_grade_and_gp(70.0)[1], 3.2)

        # 60-69.9 -> B
        self.assertEqual(calculate_grade_and_gp(65.0)[0], "B")
        self.assertEqual(calculate_grade_and_gp(60.0)[1], 2.8)

        # 50-59.9 -> C+
        self.assertEqual(calculate_grade_and_gp(55.0)[0], "C+")
        self.assertEqual(calculate_grade_and_gp(50.0)[1], 2.4)

        # 40-49.9 -> C
        self.assertEqual(calculate_grade_and_gp(45.0)[0], "C")
        self.assertEqual(calculate_grade_and_gp(40.0)[1], 2.0)

        # 35-39.9 -> D
        self.assertEqual(calculate_grade_and_gp(36.0)[0], "D")
        self.assertEqual(calculate_grade_and_gp(35.0)[1], 1.6)

        # Below 35 -> NG
        self.assertEqual(calculate_grade_and_gp(34.9)[0], "NG")
        self.assertEqual(calculate_grade_and_gp(20.0)[1], 0.0)

    def test_subject_theory_practical_evaluation(self):
        # Theory 75, Practical 25, Credit 4.0
        # Passing: 60/75 (80% A), 22/25 (88% A) -> Total 82/100 (82% A)
        res = calculate_subject_evaluation(60.0, 75.0, 22.0, 25.0, 4.0)
        self.assertEqual(res['theory_grade'], "A")
        self.assertEqual(res['practical_grade'], "A")
        self.assertEqual(res['final_grade'], "A")
        self.assertEqual(res['final_gp'], 3.6)
        self.assertEqual(res['weighted_gp'], 14.4)

        # Theory fail condition: Theory 25/75 (33.3% < 35%), Practical 24/25 (96%)
        # Total is 49/100 (49% C), but under CDC 2078/2080 theory is below 35% -> NG!
        res_ng = calculate_subject_evaluation(25.0, 75.0, 24.0, 25.0, 4.0)
        self.assertEqual(res_ng['final_grade'], "NG")
        self.assertEqual(res_ng['final_gp'], 0.0)

class TestDatabaseAndAPIIntegrity(unittest.TestCase):
    
    def test_school_info_exists(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM school_info WHERE id = 1;")
        info = cur.fetchone()
        self.assertIsNotNone(info)
        self.assertIn("Shree Sagarmatha Secondary School", info['name_en'])
        self.assertEqual(info['established_bs'], 2034)
        conn.close()

    def test_classes_and_subjects_seeded(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM classes;")
        classes_count = cur.fetchone()['count']
        self.assertGreaterEqual(classes_count, 12)

        cur.execute("SELECT COUNT(*) as count FROM subjects;")
        sub_count = cur.fetchone()['count']
        self.assertGreaterEqual(sub_count, 20)
        conn.close()

    def test_students_and_marks_integrity(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Active';")
        st_count = cur.fetchone()['count']
        self.assertGreaterEqual(st_count, 10)

        # Verify Class 10 student Aayush Adhikari marks
        cur.execute("SELECT id FROM students WHERE reg_no = 'SSS-2081-1001';")
        sid = cur.fetchone()['id']
        cur.execute("SELECT COUNT(*) as count FROM marks WHERE student_id = ?;", (sid,))
        marks_count = cur.fetchone()['count']
        self.assertGreaterEqual(marks_count, 6)
        conn.close()

    def test_financials_seeded(self):
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as count FROM invoices;")
        inv_count = cur.fetchone()['count']
        self.assertGreaterEqual(inv_count, 5)

        cur.execute("SELECT COUNT(*) as count FROM payments;")
        pay_count = cur.fetchone()['count']
        self.assertGreaterEqual(pay_count, 4)

        cur.execute("SELECT COUNT(*) as count FROM expenses;")
        exp_count = cur.fetchone()['count']
        self.assertGreaterEqual(exp_count, 5)
        conn.close()

if __name__ == '__main__':
    unittest.main()
