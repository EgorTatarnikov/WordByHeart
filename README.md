# <img src="https://raw.githubusercontent.com/EgorTatarnikov/WordByHeart/main/src/logo/WordByHeart_v2.svg" width="32" height="32" alt="wt badge"> Word by Heart

Приложение для подготовки лексики к изучению, необходимой для прочтения конкретной книги или просмотра сериала на иностранном языке.

В основе приложения лежит **NLP-pipeline**, который:

- анализирует текст: считает частоты, определяет леммы, части речи и грамматические признаки;
- выбирает ключевые слова: наиболее частые и специфичные для этого текста;
- дополняет лексику учебными грамматическими формами;
- строит IPA-транскрипцию;
- переводит слова с учётом конкретных предложений из книги;
- формирует таблицы и двусторонние карточки для изучения.

В результате **Word by Heart** превращает сырой текст в готовый набор слов для изучения и повторения.

Проект вырос из практической методики, где вместо абстрактной цели «выучить язык» ставится конкретная задача - прочитать книгу или посмотреть сериал.<br>
Изучение ограниченного набора слов, которые действительно важны для понимания выбранного текста, позволяет быстрее перейти к контенту на иностранном языке.<br>
Чтение любимых книг и просмотр сериалов в оригинале приносят удовольствие, дают ощущение прогресса и поддерживают мотивацию к дальнейшему изучению языка.

## Установка

### 1. Установите Python

Нужен Python 3.11 или новее. Проект проверен на Python 3.12. Установщик доступен на [официальном сайте Python](https://www.python.org/downloads/).

### 2. Установите eSpeak NG

eSpeak NG нужен для IPA-транскрипции. Проект проверен на eSpeak NG 1.52.0. Установщик доступен в [официальных релизах eSpeak NG](https://github.com/espeak-ng/espeak-ng/releases).

### 3. Клонируйте проект и создайте виртуальное окружение

В папке, где будет находиться приложение, откройте терминал и выполните:

```bash
git clone https://github.com/EgorTatarnikov/WordByHeart.git
cd WordByHeart
python -m venv .venv
```

### 4. Установите библиотеки и модели

Полный список Python-зависимостей указан в [pyproject.toml](pyproject.toml).

Windows:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m spacy download en_core_web_trf
python -m spacy download es_dep_news_trf
```

Linux/macOS:

```bash
source .venv/bin/activate
python -m pip install -e ".[test]"
python -m spacy download en_core_web_trf
python -m spacy download es_dep_news_trf
```

## Настройка

В корне проекта лежит файл `.env`. В нём уже указаны стандартные пути к eSpeak NG для Windows. Если eSpeak NG установлен в другую папку, измените `PHONEMIZER_ESPEAK_LIBRARY` и `PHONEMIZER_ESPEAK_DATA_PATH`.

Для английской книги используйте [config/demo_en.yaml](config/demo_en.yaml), для испанской — [config/demo_es.yaml](config/demo_es.yaml).

Рабочие папки `data/work`, `data/cache` и `data/output` создаются автоматически.

## Запуск демо

Английский текст:

```powershell
python -m src.main --config config\demo_en.yaml run-all data\input\demo_en.txt
```

Испанский текст:

```powershell
python -m src.main --config config\demo_es.yaml run-all data\input\demo_es.txt
```

## Запуск на своей книге

Скопируйте UTF-8 TXT-файл книги в `data/input/` или передайте к нему другой путь. Затем замените последний аргумент команды:

```powershell
python -m src.main --config config\demo_en.yaml run-all data\input\my_book.txt
```

## Перевод через OpenAI API

По умолчанию перевод выключен, поэтому демо можно запустить без OpenAI API.

Чтобы включить перевод:

1. Откройте `.env`.
2. Раскомментируйте строку `OPENAI_API_KEY=` и укажите API key.
3. В нужном config измените:

```yaml
translation:
  enabled: true
```

В demo-config указана модель `gpt-5.6-luna`. При необходимости замените `translation.model` на модель, доступную вашему OpenAI API-проекту.

## Результат

После запуска появляются:

- таблица лемм в XLSX и CSV;
- таблица словоформ в XLSX и CSV;
- DOCX-файл с двусторонними карточками.

Таблицы можно самостоятельно изучать, фильтровать и использовать в других задачах. Карточки можно распечатать, разрезать и использовать для изучения и повторения.

## Как работает отбор слов

```text
TXT
→ preprocessing
→ spaCy NLP
→ aggregation
→ reference frequency / specificity
→ grammar enrichment
→ IPA
→ translation
→ validation
→ export
→ cards
```

Pipeline поддерживает повторный запуск. Он записывает состояние stages в manifest, не запускает повторно актуальные stages, хранит результаты NLP в Parquet и кэширует IPA и переводы в SQLite.

Основные параметры отбора находятся в разделе `translation` config:

```yaml
cumulative_coverage_limit: 90
specificity_threshold: 10
min_book_occurrences: 4
```

- `cumulative_coverage_limit` — процент текста, который покрывает частотный набор лемм. Значение `90` означает, что в перевод и карточки войдёт минимальный частотный набор, покрывающий не менее 90% словоупотреблений текста.
- `specificity_threshold` — дополнительный порог важности слова для конкретной книги. Specificity сравнивает относительную частоту слова в книге с reference frequency из `wordfreq`. Слова со значением не ниже порога добавляются, даже если не вошли в частотный набор.
- `min_book_occurrences` — минимальное число вхождений слова в книге для добавления по specificity. Значение `4` защищает от случайных редких слов.

Другие полезные параметры:

- `nlp.model` — модель spaCy;
- `pronunciation.language` — вариант eSpeak NG: `es` для испанского, `en-gb` для британского английского;
- `translation.enabled` — включение перевода через API;
- `cards.enabled` — генерация карточек;
- `cards.template` — путь к Word-шаблону карточек;
- `paths.work`, `paths.cache`, `paths.output` — папки промежуточных результатов, кэшей и готовых файлов.

Для запуска отдельной стадии используйте её имя вместо `run-all`:

```powershell
python -m src.main --config config\demo_en.yaml status
python -m src.main --config config\demo_en.yaml ipa --force
python -m src.main --config config\demo_en.yaml cards
```

`status` показывает готовность stages. `--force` запускает указанную stage заново и делает зависимые результаты устаревшими.

## Уже известные слова

`my_dictionary_en.xlsx` и `my_dictionary_es.xlsx` содержат известные слова в первом столбце. Установите `known_dictionary.enabled: true` в соответствующем config, чтобы не создавать карточки для этих лемм. Список влияет только на stage `cards`.

## Лицензия

Исходный код распространяется по PolyForm Noncommercial 1.0.0. Документация, `table.docx` и результаты работы — по CC BY-NC 4.0. При некоммерческом использовании необходимо сохранить attribution: Egor Tatarnikov и ссылку на [WordByHeart](https://github.com/EgorTatarnikov/WordByHeart). Эти лицензии относятся только к оригинальным материалам проекта.
