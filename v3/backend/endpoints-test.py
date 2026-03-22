import requests

BASE_URL = "http://127.0.0.1:8000"

# --- 1️⃣ Login to get JWT ---
login_payload = {
    "username": "student",   # change this
    "password": "student123"    # change this
}

print("🔹 Logging in...")
try:
    r = requests.post(f"{BASE_URL}/login", json=login_payload)
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        print("❌ Login succeeded but no token returned")
        exit()
    print("✅ Login successful, token received")
except requests.HTTPError as e:
    print("❌ Login failed:", e)
    exit()

headers = {"Authorization": f"Bearer {token}"}

# --- 2️⃣ Test sessions endpoint ---
print("\n🔹 Testing /sessions...")
r = requests.get(f"{BASE_URL}/sessions", headers=headers)
if r.status_code == 200:
    print("✅ /sessions OK:", r.json())
else:
    print("❌ /sessions failed:", r.status_code, r.text)

# --- 3️⃣ Test classes endpoint ---
print("\n🔹 Testing /classes...")
r = requests.get(f"{BASE_URL}/classes", headers=headers)
if r.status_code == 200:
    print("✅ /classes OK:", r.json())
else:
    print("❌ /classes failed:", r.status_code, r.text)

# --- 4️⃣ Test PDF fetch ---
sample_pdf = "D:/GPT/ai-student-companion/v3/knowledge_base/Class 8/English/Text Books/QR0849/1.pdf"
print("\n🔹 Testing /pdf endpoint...")
r = requests.get(f"{BASE_URL}/pdf", headers=headers, params={"path": sample_pdf})
if r.status_code == 200:
    print("✅ PDF fetch OK, content-type:", r.headers.get("content-type"))
else:
    print("❌ PDF fetch failed:", r.status_code, r.text)