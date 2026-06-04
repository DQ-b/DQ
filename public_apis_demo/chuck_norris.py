import urllib.request
import json

url = "https://api.chucknorris.io/jokes/random"

with urllib.request.urlopen(url) as response:
    data = json.loads(response.read().decode())

print(data["value"])
