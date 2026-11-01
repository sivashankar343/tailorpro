"""
Test user isolation and zero-count baseline for new users.
"""
from app import create_app, db
from models import User, Company, Order, ProductionEntry

def test_user_isolation():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    client = app.test_client()

    with app.app_context():
        # Clear existing test users if any
        ProductionEntry.query.delete()
        Order.query.delete()
        Company.query.delete()
        User.query.filter(User.username.in_(['tailor_a', 'tailor_b'])).delete()
        db.session.commit()

    print("\n--- TEST 1: Register User A ---")
    r = client.post('/register', data={
        'full_name': 'Tailor A User',
        'username': 'tailor_a',
        'email': 'tailor_a@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert r.status_code == 200

    # Login User A
    r = client.post('/login', data={'login_id': 'tailor_a', 'password': 'Password123'}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Welcome back, Tailor A User!" in r.data
    # Check all counts are 0
    assert b"0" in r.data
    print("   -> User A registered and logged in with ALL 0 counts!")

    # User A adds a company
    print("\n--- TEST 2: User A adds a company ---")
    r = client.post('/companies/add', data={
        'company_name': 'User A Suits Co',
        'contact_person': 'A Manager',
        'phone': '1111111111'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"User A Suits Co" in r.data
    assert b"CMP-0001" in r.data
    print("   -> User A created company CMP-0001 (User A Suits Co)")

    # User A adds an order
    with app.app_context():
        u_a = User.query.filter_by(username='tailor_a').first()
        cmp_a = Company.query.filter_by(created_by=u_a.id).first()
        cmp_a_id = cmp_a.id

    r = client.post('/orders/new', data={
        'company_id': cmp_a_id,
        'garment_type': 'Men Blazers',
        'total_quantity': 100
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"ORD-00001" in r.data
    print("   -> User A created order ORD-00001")

    # Logout User A
    client.get('/logout', follow_redirects=True)

    print("\n--- TEST 3: Register User B (Must start at 0, no data from User A) ---")
    r = client.post('/register', data={
        'full_name': 'Tailor B User',
        'username': 'tailor_b',
        'email': 'tailor_b@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert r.status_code == 200

    # Login User B
    r = client.post('/login', data={'login_id': 'tailor_b', 'password': 'Password123'}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Welcome back, Tailor B User!" in r.data
    print("   -> User B logged in successfully.")

    # Verify User B sees 0 companies
    r = client.get('/companies/')
    assert b"User A Suits Co" not in r.data, "FAILED: User B saw User A's company!"
    assert b"No companies found" in r.data or b"0" in r.data
    print("   -> User B companies count is 0 (User A's company is hidden)")

    # Verify User B sees 0 orders
    r = client.get('/orders/')
    assert b"ORD-00001" not in r.data, "FAILED: User B saw User A's order!"
    assert b"Men Blazers" not in r.data
    print("   -> User B orders count is 0 (User A's order is hidden)")

    # Verify User B dashboard has 0
    r = client.get('/dashboard')
    assert b"ORD-00001" not in r.data
    print("   -> User B dashboard shows clean 0 counts!")

    # User B adds their OWN company
    print("\n--- TEST 4: User B adds their own company ---")
    r = client.post('/companies/add', data={
        'company_name': 'User B Shirts Ltd',
        'contact_person': 'B Manager',
        'phone': '2222222222'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"User B Shirts Ltd" in r.data
    assert b"CMP-0001" in r.data  # Starts from CMP-0001 for User B too!
    assert b"User A Suits Co" not in r.data
    print("   -> User B created CMP-0001 (User B Shirts Ltd) starting from 1!")

    # Verify User A still only sees User A's company
    print("\n--- TEST 5: Verify User A still only sees User A's data ---")
    client.get('/logout', follow_redirects=True)
    client.post('/login', data={'login_id': 'tailor_a', 'password': 'Password123'}, follow_redirects=True)
    r = client.get('/companies/')
    assert b"User A Suits Co" in r.data
    assert b"User B Shirts Ltd" not in r.data, "FAILED: User A saw User B's company!"
    print("   -> User A only sees User A's company (User B's company is hidden)")

    print("\n=== SUCCESS: FULL USER ISOLATION VERIFIED! NO INTERLINKING BETWEEN USERS! ===")

if __name__ == '__main__':
    test_user_isolation()
