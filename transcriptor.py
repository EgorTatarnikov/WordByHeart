import json
   
"""
# Пример чтения первых 100 строк из файла и записи их в другой файл

with open("lines.txt", 'w', encoding="utf-8") as outfile:
    with open("raw-wiktextract-data.jsonl", encoding="utf-8") as infile:
        for i in range(100):
            line = infile.readline()
            s = json.loads(line)
            #print(json.dumps(s, indent=4))
            outfile.write(json.dumps(s, indent=4))
"""
      
def extract_word(line):
    data = json.loads(line)
    

    if data.get("lang") == "English":
        
        # извлекаем слово
        word = data.get("word", "")

        # извлекаем IPA транскрипцию
        ipa = [] 
        sounds = data.get("sounds", [])
        
        # сначала собираем все RP IPA
        for s in sounds:
            if "ipa" in s and s["ipa"] not in ipa: 
                if "tags" in s and "Received-Pronunciation" in s["tags"]:
                    ipa.append(s["ipa"])
        
        # если RP нет, берём первый попавшийся IPA
        if not ipa:
            for s in sounds:
                if "ipa" in s:
                    ipa.append(s["ipa"])
                    break 
        
        # извлекаем переводы на русский язык и смыслы слов
        translation = []
        sense = []
        translations = data.get("translations", [])
        
        for t in translations:
            
            if t.get("lang") == "Russian":
                
                ru_word = t.get("word", None)
                if ru_word and ru_word not in translation:
                    translation.append(ru_word)
                    
                ru_word_sense = t.get("sense", None)
                if ru_word_sense and ru_word_sense not in sense:
                    sense.append(ru_word_sense)
                    
        # извлекаем примеры использования слова
        senses = data.get("senses", [])
        example = []
        
        for s in senses:
            for e in s.get("examples", []):  
                text = e.get("text")
                if text and len(text) < 120 and text not in example: 
                    example.append(text)
        
        return word, ipa, translation, sense, example
    
    
'''''
# Пример извлечения через extract_word первых слов и записи их в файл 
with open("lines.txt", 'w', encoding="utf-8") as outfile:
    with open("raw-wiktextract-data.jsonl", encoding="utf-8") as infile:
        for i in range(10):
            line = infile.readline()
            word = extract_word(line)
            if word:
                outfile.write(f"{word}\n")
                print(word)
'''               


'''
# Подсчёт количества слов (JSON-объектов) в файле
count = 0 

with open("raw-wiktextract-data.jsonl", encoding="utf-8") as f:
    for line_number, line in enumerate(f, 1):
        line = line.strip()  # убираем пробелы и \n
        if not line:
            continue  # пропускаем пустые строки

        count += 1  # увеличиваем счётчик

print("Количество слов (JSON-объектов) в файле:", count)''' # Вывод: 10440227 слов

'''
# Обработка первых строк и запись в JSON-файл
with open("raw-wiktextract-data.jsonl", encoding="utf-8") as infile, \
     open("processed_words.jsonl", "w", encoding="utf-8") as outfile:
    for i in range(10):
        line = infile.readline()
        line = line.strip()
        if not line:
            continue
        
        word = extract_word(line)
        if word:
            json.dump(word, outfile, ensure_ascii=False)
            outfile.write("\n")  # важен переход на новую строку
            print(word)
            '''
            


# Полная обработка файла и запись результатов в новый файл
'''
with open("raw-wiktextract-data.jsonl", encoding="utf-8") as infile, \
     open("E:\processed_words.jsonl", "w", encoding="utf-8") as outfile:
    
    for line_number, line in enumerate(infile, 1):
        line = line.strip()
        if not line:
            continue

        data = extract_word(line)
        if data:  # если функция вернула что-то
            json.dump(data, outfile, ensure_ascii=False)
            outfile.write("\n")  # важен переход на новую строку

        if line_number % 10000 == 0:
            print(f"Обработано {line_number} строк")
'''


'''
# Проверим записанный файл
print('\nПервые строки из processed_words.jsonl:')

with open("processed_words.jsonl", encoding="utf-8") as f:
    for i in range(5):
        line = f.readline()
        print(line.strip())'''
        
'''     
#Подсчёт количества слов (JSON-объектов) в файле
count = 0 

with open("E:\processed_words.jsonl", encoding="utf-8") as f:
    for line_number, line in enumerate(f, 1):
        line = line.strip()  # убираем пробелы и \n
        if not line:
            continue  # пропускаем пустые строки

        count += 1  # увеличиваем счётчик

print("Количество слов (JSON-объектов) в файле:", count)    # Вывод: 1442009 слов
'''