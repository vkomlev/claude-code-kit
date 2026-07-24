# Рецепты промптов для генерации изображений

## Универсальная структура (применима к любой платформе)
```
[Subject] + [Action/Scene] + [Style/Medium] + [Composition] + [Lighting] +
[Color palette] + [Mood] + [Technical params]
```

### Расшифровка слотов
| Слот | Что туда писать | Пример |
|------|-----------------|--------|
| Subject | Главный объект, кто/что | «молодая женщина-программист» |
| Action/Scene | Что делает, где | «работает за ноутбуком в кофейне» |
| Style/Medium | Жанр, материал | «фотореализм / oil painting / 3D render / pixel art» |
| Composition | План, ракурс, кадрирование | «medium shot, rule of thirds, low angle» |
| Lighting | Источник, направление, качество | «golden hour, soft window light, rim light» |
| Color palette | Доминанты | «warm earth tones / cool teal and orange / monochrome blue» |
| Mood | Эмоция, атмосфера | «introspective, calm, energetic, melancholic» |
| Technical | DOF, плёнка, объектив | «shallow depth of field, 85mm, Kodak Portra 400» |

## Midjourney v6/v7
**Особенности:**
- Понимает natural language (полные фразы), не только теги
- Параметры через двойной дефис в конце: `--ar 16:9 --style raw --v 7`
- Negative prompt — только через `--no [objects]`, не «without X» в тексте
- Веса через `::` — `red car::2 blue sky::1`

**Базовый шаблон:**
```
[full natural sentence describing scene], [style modifiers], [lighting], [mood] --ar 3:2 --style raw --v 7
```

**Пример:**
```
A young software engineer working late at night in a minimalist home office,
warm desk lamp casting soft shadows, multiple monitors glowing,
cinematic photography, shallow depth of field, Kodak Portra 400 film grain,
introspective mood --ar 16:9 --style raw --v 7
```

**Полезные параметры:**
- `--ar W:H` — соотношение сторон
- `--style raw` — выключает Midjourney «эстетизацию», ближе к фотографии
- `--stylize 100..1000` — насколько креативно (по умолчанию 100)
- `--chaos 0..100` — вариативность между 4 вариантами
- `--no [objects]` — что исключить

## DALL-E 3 (через ChatGPT или API)
**Особенности:**
- Лучше всего работает с **полными грамотными предложениями**
- Следует инструкциям очень буквально — важна точная формулировка
- Хорошо обрабатывает текст внутри изображения (надписи)
- Negative prompt отсутствует — переформулировать в позитив

**Базовый шаблон:**
```
A [composition] of [subject] [action] in [setting].
The image is in the style of [style]. Lighting is [lighting].
Color palette is [colors]. Mood is [mood].
[Technical details if photo]. [Aspect / format].
```

**Пример:**
```
A medium-wide cinematic photograph of a young software engineer typing on a laptop
at a wooden desk in a softly lit home office at night. The image is in the style of
contemporary documentary photography. Lighting is warm and motivated by a single
desk lamp on the left, creating gentle rim light. Color palette is warm amber and
deep brown shadows. Mood is focused and introspective. Shot on 85mm lens with
shallow depth of field. Wide 16:9 aspect ratio.
```

## Stable Diffusion / Flux
**Особенности:**
- Принимает comma-separated теги, не обязательны полные предложения
- Поддерживает **weighting**: `(word:1.3)` усиливает, `(word:0.7)` ослабляет
- **Negative prompt** — отдельное поле, явно поддерживается
- Чувствителен к порядку: первые теги важнее
- LoRA и checkpoints добавляют стиль вне промпта

**Базовый шаблон:**
```
Positive: [subject], [style tags], [composition tags], [lighting tags], [quality tags]
Negative: [unwanted elements, defects, artifacts]
```

**Пример:**
```
Positive:
(young female software engineer:1.2), working on laptop, modern home office at night,
warm desk lamp, multiple monitors glowing, (cinematic photography:1.3),
(shallow depth of field:1.2), 85mm lens, Kodak Portra 400 film, soft rim light,
introspective mood, highly detailed, professional photography

Negative:
blurry, low quality, distorted hands, extra fingers, watermark, text, signature,
cartoon, anime, oversaturated, deformed, ugly
```

**Полезные теги качества:** `masterpiece, best quality, highly detailed, 8k, sharp focus`
**Стандартный negative:** `low quality, blurry, distorted, watermark, signature, jpeg artifacts, deformed`

## Flux (Black Forest Labs)
**Особенности:**
- Ближе к DALL-E по поведению — любит natural language
- Отлично рендерит текст в изображениях
- Меньше нужен negative prompt
- Не любит чрезмерное количество тегов

**Шаблон:** как DALL-E 3, но можно добавлять weight-теги SD-стиля для критичных элементов.

## Чеклист image-промпта
- [ ] Subject конкретен (не «человек», а «молодая женщина 25 лет, азиатка, в очках»)
- [ ] Указан стиль/медиум (фото / иллюстрация / 3D / painting)
- [ ] Композиция (план, ракурс, кадрирование)
- [ ] Свет (источник, направление, качество)
- [ ] Цветовая палитра или настроение цвета
- [ ] Технические параметры (если фото — объектив, плёнка, DOF)
- [ ] Aspect ratio задан явно
- [ ] Negative prompt (только если платформа поддерживает)
- [ ] Нет противоречий («тёмная ночь» + «яркий солнечный свет»)

## Анти-паттерны
- Списки прилагательных без структуры: «красивый, потрясающий, удивительный»
- Противоречивые стили: «фотореализм в стиле акварели»
- Слишком много объектов в одном кадре (>3 главных) — модель путается
- Указание брендов и реальных лиц без необходимости — часто блокируется
- «Без X» в позитивном промпте — добавлять X в negative или переформулировать
