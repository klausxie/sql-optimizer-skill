#!/usr/bin/env python3
"""Test MySQL connectivity and EXPLAIN parsing."""

import sys
import pymysql


def test_mysql_connection():
    print("Testing MySQL connection...")
    try:
        conn = pymysql.connect(
            host="localhost",
            port=3306,
            user="root",
            password="root",
            database="sqlopt_test",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
        print("✓ MySQL connection successful")
        cursor = conn.cursor()

        # Test basic query
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"✓ Basic query: {result}")

        # Test EXPLAIN
        cursor.execute("EXPLAIN SELECT * FROM users WHERE status = 'ACTIVE'")
        explain_result = cursor.fetchone()
        print(f"✓ EXPLAIN works: {explain_result}")

        # Test table exists
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"✓ Tables: {[t['Tables_in_sqlopt_test'] for t in tables]}")

        conn.close()
        return True
    except pymysql.err.OperationalError as e:
        print(f"✗ MySQL connection failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_db_connector():
    print("\nTesting sqlopt MySQL DBConnector...")
    try:
        from sqlopt.common.db_connector import MySQLConnector

        db = MySQLConnector(
            host="localhost",
            port=3306,
            db="sqlopt_test",
            user="root",
            password="root",
        )
        print("✓ DBConnector created successfully")

        # Test EXPLAIN
        db.connect()
        result = db.execute_explain("SELECT * FROM users WHERE status = 'ACTIVE' AND type = 'VIP'")
        print(f"✓ DBConnector.execute_explain works: {result}")
        db.disconnect()

        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ DBConnector error: {e}")
        return False


if __name__ == "__main__":
    success = True

    if not test_mysql_connection():
        success = False

    if not test_db_connector():
        success = False

    sys.exit(0 if success else 1)
