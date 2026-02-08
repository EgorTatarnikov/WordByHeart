import gzip
import os
import csv
import string

DATA_DIR = r"E:\google_1grams_eng"  # папка с .gz файлами
TOP_K = 1000000                      # сколько топ слов сохранить

# Словарь для подсчёта слов
word_counts = {}

# Получаем список всех файлов .gz
gz_files = [f for f in os.listdir(DATA_DIR) if f.endswith(".gz")]
gz_files.sort()

# Множество символов пунктуации для фильтра
punctuation = set(string.punctuation)

# Для каждого файла .gz
for gz_file in gz_files:
    print("Processing:", gz_file)
    file_path = os.path.join(DATA_DIR, gz_file)
    
    with gzip.open(file_path, "rt", encoding="utf-8", errors="ignore") as f:
        # Читаем файл построчно (каждая строка это: слово \t год \t количество_упоминаний \t количество_книг_с_этим_словом)
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue

            word, year, match_count = parts[:3]

            # приводим к нижнему регистру
            word = word.lower()

            # пропускаем слова с любой пунктуацией
            if any(char in punctuation for char in word):
                continue
            # пропускаем слова с цифрами
            if any(char.isdigit() for char in word):
                continue

            # увеличиваем счётчик слова
            if word in word_counts:
                word_counts[word] += int(match_count)
            else:
                word_counts[word] = int(match_count)


# Создаём список из всех пар (слово, частота)
word_items = list(word_counts.items())

# Сортируем список по частоте по убыванию
sorted_word_items = sorted(word_items, key=lambda pair: pair[1], reverse=True)

# Берём только первые TOP_K элементов
sorted_words = sorted_word_items[:TOP_K]

# Cуммарное количество всех упоминаний всех слов
count_sum = sum(word_counts.values())

# Относительная частота слова
freq_dict = []
for word, count in sorted_words:
    rel_freq = count / count_sum
    # Сохраняем в список кортежей: (слово, абсолютная частота, относительная частота)
    freq_dict.append((word, count, rel_freq))

# Выводим результат в CSV
output_file = os.path.join(DATA_DIR, f"top_{TOP_K}_words.csv")
with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["word", "total_match_count", "relative_frequency"])
    for word, count, rel_freq in freq_dict:
        writer.writerow([word, count, rel_freq])

print("Done! Saved to:", output_file)