import sys
sys.path.insert(0, r"C:\Users\advai\OneDrive\Documents\Computer\Capstone\EPARS\code")

# Import Flask app
from app import app

# Create a test client
client = app.test_client()

print("="*80)
print("=== TESTING /performance/ ENDPOINT ===")
print("="*80)

response = client.get('/performance/')

print(f"\nStatus Code: {response.status_code}")
print(f"Content-Type: {response.content_type}")
print(f"Content Length: {len(response.data)} bytes")

# Parse the HTML and look for employee names
html = response.data.decode('utf-8')

# Find the table rows
import re
emp_rows = re.findall(r'<tr class="emp-row"[^>]*>.*?<td class="emp-name">([^<]+)</td>', html, re.DOTALL)

print(f"\nEmployees found in HTML table (first 20):")
for i, name in enumerate(emp_rows[:20]):
    print(f"  {i+1}. {name}")

# Also check the raw data-id values
emp_ids = re.findall(r'data-id="([^"]+)"', html)
print(f"\nTotal employee rows in table: {len(emp_ids)}")
print(f"First 10 employee IDs: {emp_ids[:10]}")

# Save the HTML to a file for inspection
with open('performance_page.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f"\nFull HTML saved to: performance_page.html")