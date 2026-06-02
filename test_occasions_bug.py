from datetime import datetime
from desktop_pet.occasions import today_key

test_date = datetime(2026, 1, 5)
result1 = today_key(test_date, "1-5")
result2 = today_key(test_date, "01-05")
md = test_date.strftime("%m-%d")

print("Input 1-5, Result:", result1)
print("Input 01-05, Result:", result2)
print("Today strftime:", md)
print("1-5 == md:", "1-5" == md)
print("01-05 == md:", "01-05" == md)
