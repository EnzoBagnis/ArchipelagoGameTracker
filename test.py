import requests
token = "j5HvaH4lABpWuTsvRM2peh62xxl4OOUZbEAJezD1"
r = requests.get(
    "https://api.itch.io/profile/owned-keys",
    headers={"Authorization": f"Bearer {token}"},
    params={"page": 1},
    timeout=15
)
print(r.status_code)
print(r.text[:500])