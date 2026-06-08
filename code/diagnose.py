import pandas as pd
import sys

sys.path.insert(0, r"C:\Users\advai\OneDrive\Documents\Computer\Capstone\EPARS\code")

from modules.performance.model import df_display

print("="*80)
print("=== CHECKING WHY get_employee_list() IS WRONG ===")
print("="*80)

# Simulate what get_employee_list does
latest = (
    df_display.sort_values("review_date", ascending=False)
    .drop_duplicates(subset="employee_id")
)

print(f"\nTotal rows in df_display: {len(df_display)}")
print(f"Unique employees: {df_display['employee_id'].nunique()}")
print(f"Rows kept after drop_duplicates: {len(latest)}")

# Check which employees have multiple reviews
review_counts = df_display['employee_id'].value_counts()
employees_with_multiple_reviews = review_counts[review_counts > 1]
print(f"\nEmployees with multiple reviews: {len(employees_with_multiple_reviews)}")
print(f"Max reviews per employee: {review_counts.max()}")

# Check a specific employee that should have realistic name
print("\n" + "="*80)
print("=== CHECKING EMPLOYEE EMP109 (should be Nancy Scott) ===")
print("="*80)

emp109_all = df_display[df_display['employee_id'] == 'EMP109'].sort_values("review_date", ascending=False)
print(f"\nTotal reviews for EMP109: {len(emp109_all)}")
print("\nAll reviews for EMP109:")
print(emp109_all[['employee_id', 'first_name', 'last_name', 'review_date', 'overall_performance_score']])

# Check what drop_duplicates picks
emp109_latest = latest[latest['employee_id'] == 'EMP109']
if not emp109_latest.empty:
    print(f"\nWhat drop_duplicates picked for EMP109:")
    print(f"  Name: {emp109_latest.iloc[0]['first_name']} {emp109_latest.iloc[0]['last_name']}")
    print(f"  Review Date: {emp109_latest.iloc[0]['review_date']}")

# Check another realistic name
print("\n" + "="*80)
print("=== CHECKING EMPLOYEE EMP1065 (should be Meera Miller) ===")
print("="*80)

emp1065_all = df_display[df_display['employee_id'] == 'EMP1065'].sort_values("review_date", ascending=False)
print(f"\nTotal reviews for EMP1065: {len(emp1065_all)}")
print("\nAll reviews for EMP1065:")
print(emp1065_all[['employee_id', 'first_name', 'last_name', 'review_date', 'overall_performance_score']])

emp1065_latest = latest[latest['employee_id'] == 'EMP1065']
if not emp1065_latest.empty:
    print(f"\nWhat drop_duplicates picked for EMP1065:")
    print(f"  Name: {emp1065_latest.iloc[0]['first_name']} {emp1065_latest.iloc[0]['last_name']}")
    print(f"  Review Date: {emp1065_latest.iloc[0]['review_date']}")

# Check how many employees are showing as "Aarna"
print("\n" + "="*80)
print("=== HOW MANY 'AARNA' IN latest? ===")
print("="*80)
aarna_count = len(latest[latest['first_name'] == 'Aarna'])
print(f"Employees with first_name='Aarna': {aarna_count}")

print("\nSample of Aarna employees:")
aarna_samples = latest[latest['first_name'] == 'Aarna'].head(10)
print(aarna_samples[['employee_id', 'first_name', 'last_name', 'review_date']])