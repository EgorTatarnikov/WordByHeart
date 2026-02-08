import requests
import os

base_url = "https://storage.googleapis.com/books/ngrams/books/"
out_dir = r"E:\google_1grams_eng"
os.makedirs(out_dir, exist_ok=True)

letters = "abcdefghijklmnopqrstuvwxyz"

indexes = []
for i in range(10):
    indexes.append(i)
for letter in letters:
    indexes.append(letter)
indexes.append('other')
indexes.append('pos')
indexes.append('punctuation')



for index in indexes:
    fname = f"googlebooks-eng-all-1gram-20120701-{index}.gz"
    url = base_url + fname
    path = os.path.join(out_dir, fname)

    print("Downloading", fname)
    r = requests.get(url, stream=True)

    if r.status_code == 200:
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
    else:
        print("Not found:", fname)