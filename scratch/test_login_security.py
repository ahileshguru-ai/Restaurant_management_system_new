import urllib.request
import urllib.error
import json
import sqlite3

BASE_URL = "http://127.0.0.1:8000"

def api_call(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return response.status, json.loads(res_body) if res_body else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            parsed = json.loads(err_body)
        except Exception:
            parsed = {"detail": err_body}
        return e.code, parsed

def run_tests():
    print("--- 1. Testing login with matching role ---")
    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "waiter_rahul",
        "password": "waiter123",
        "expected_role": "Waiter"
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    waiter_token = res["access_token"]
    print("[OK] Waiter login succeeded.")

    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "chef_vikram",
        "password": "chef123",
        "expected_role": "Chef"
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    chef_token = res["access_token"]
    print("[OK] Chef login succeeded.")

    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "kitchenmgr",
        "password": "kitchen123",
        "expected_role": "Kitchen Manager"
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    km_token = res["access_token"]
    print("[OK] Kitchen Manager login succeeded.")

    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "shopmanager",
        "password": "manager123",
        "expected_role": "Shop Manager"
    })
    assert status == 200, f"Expected 200, got {status}: {res}"
    sm_token = res["access_token"]
    print("[OK] Shop Manager login succeeded.")

    print("\n--- 2. Testing cross-role login denial (e.g. Waiter trying to login under Chef) ---")
    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "waiter_rahul",
        "password": "waiter123",
        "expected_role": "Chef"
    })
    assert status == 403, f"Expected 403, got {status}: {res}"
    print(f"[OK] Cross-role denied correctly: {res['detail']}")

    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "kitchenmgr",
        "password": "kitchen123",
        "expected_role": "Shop Manager"
    })
    assert status == 403, f"Expected 403, got {status}: {res}"
    print(f"[OK] Cross-role denied correctly: {res['detail']}")

    print("\n--- 3. Testing invalid password ---")
    status, res = api_call("/api/auth/login", method="POST", data={
        "username": "shopmanager",
        "password": "wrongpassword",
        "expected_role": "Shop Manager"
    })
    assert status == 401, f"Expected 401, got {status}: {res}"
    print("[OK] Wrong password rejected with 401.")

    print("\n--- 4. Testing authorization on /register-staff ---")
    status, res = api_call("/api/auth/register-staff", method="POST", data={
        "name": "Hacker Waiter",
        "role": "Waiter",
        "shift": "Morning Shift",
        "salary": 30000,
        "username": "hacker1",
        "password": "password123"
    }, token=waiter_token)
    assert status == 403, f"Expected 403 for Waiter, got {status}: {res}"
    print(f"[OK] Non-Shop Manager blocked from registering staff: {res['detail']}")

    status, res = api_call("/api/auth/register-staff", method="POST", data={
        "name": "KM Staff",
        "role": "Chef",
        "shift": "Morning Shift",
        "salary": 35000,
        "username": "km_created",
        "password": "password123"
    }, token=km_token)
    assert status == 403, f"Expected 403 for KM, got {status}: {res}"
    print(f"[OK] Kitchen Manager blocked from registering staff: {res['detail']}")

    print("\n--- 5. Testing authorization on /update-credentials ---")
    status, res = api_call("/api/auth/update-credentials", method="PUT", data={
        "user_id": 1,
        "new_password": "hackedpassword"
    }, token=chef_token)
    assert status == 403, f"Expected 403 for Chef, got {status}: {res}"
    print(f"[OK] Non-Shop Manager blocked from updating credentials: {res['detail']}")

    print("\n--- 6. Testing Shop Manager authorized registration and update ---")
    test_user = "test_waiter_sec"
    conn = sqlite3.connect("restaurant.db")
    c = conn.cursor()
    c.execute("SELECT UserID, EmployeeID FROM Users WHERE Username = ?", (test_user,))
    row = c.fetchone()
    if row:
        c.execute("DELETE FROM Users WHERE UserID = ?", (row[0],))
        c.execute("DELETE FROM Staff WHERE EmployeeID = ?", (row[1],))
        conn.commit()
    conn.close()

    status, res = api_call("/api/auth/register-staff", method="POST", data={
        "name": "Test Security Waiter",
        "role": "Waiter",
        "shift": "Evening Shift",
        "salary": 28000,
        "username": test_user,
        "password": "initial_password_123"
    }, token=sm_token)
    assert status == 200, f"Expected 200 for Shop Manager, got {status}: {res}"
    new_user_id = res["user_id"]
    print(f"[OK] Shop Manager successfully registered new staff: {res['message']}")

    # Shop manager updates credentials
    status, res = api_call("/api/auth/update-credentials", method="PUT", data={
        "user_id": new_user_id,
        "new_password": "updated_password_456"
    }, token=sm_token)
    assert status == 200, f"Expected 200 for Shop Manager update, got {status}: {res}"
    print(f"[OK] Shop Manager successfully updated credentials: {res['message']}")

    # The new user logs in with updated password
    status, res = api_call("/api/auth/login", method="POST", data={
        "username": test_user,
        "password": "updated_password_456",
        "expected_role": "Waiter"
    })
    assert status == 200, f"Expected 200 for new employee login, got {status}: {res}"
    print("[OK] New employee logged in with credentials created & updated by Shop Manager.")

    # Clean up test user
    conn = sqlite3.connect("restaurant.db")
    c = conn.cursor()
    c.execute("DELETE FROM Users WHERE Username = ?", (test_user,))
    conn.commit()
    conn.close()

    print("\nALL BACKEND SECURITY & AUTHENTICATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
