import requests
import json
import collections

url = "https://openmensa.org/api/v2/canteens/289/meals"

response = requests.get(url)

# Check if the request was successful (status code 200)
if response.status_code == 200:
    data = response.json()
    meal = data[0].keys()


else:
    print("Error:", response.status_code)
