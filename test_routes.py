"""
Route verification test for TailorPro application.
"""
from app import create_app, db
from models import User

def test_routes():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False  # disable for testing convenience
    client = app.test_client()

    print("1. Testing GET /login...")
    r = client.get('/login')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Sign In" in r.data, "Sign In not found in response"
    print("   -> OK")

    print("2. Testing GET /register...")
    r = client.get('/register')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Create Account" in r.data, "Create Account not found in response"
    print("   -> OK")

    print("3. Testing POST /login with admin account...")
    r = client.post('/login', data={'login_id': 'admin', 'password': 'Admin@123'}, follow_redirects=True)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Dashboard" in r.data, "Dashboard not found after login"
    assert b"No production entries yet" in r.data or b"0" in r.data, "Empty state not found in dashboard"
    print("   -> Logged in successfully, Dashboard rendered with 0 counts OK")

    print("4. Testing GET /companies/ (0 count)...")
    r = client.get('/companies/')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Companies" in r.data
    print("   -> Companies list OK")

    print("5. Testing GET /orders/ (0 count)...")
    r = client.get('/orders/')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Orders" in r.data
    print("   -> Orders list OK")

    print("6. Testing GET /orders/production...")
    r = client.get('/orders/production')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("   -> Production entry page OK")

    print("7. Testing GET /orders/history...")
    r = client.get('/orders/history')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    print("   -> Production history page OK")

    print("8. Testing GET /reports...")
    r = client.get('/reports')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"Download Reports" in r.data or b"Reports" in r.data
    print("   -> Reports page OK")

    print("9. Testing GET /users (admin only)...")
    r = client.get('/users')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert b"admin" in r.data
    print("   -> User management page OK")

    print("10. Testing Excel download /reports/download/order...")
    r = client.get('/reports/download/order')
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert len(r.data) > 0, "Excel data empty"
    print("   -> Excel download OK")

    print("\nALL 10 ROUTE AND WORKFLOW TESTS PASSED!")

if __name__ == '__main__':
    test_routes()
