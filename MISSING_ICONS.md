# Отсутствующие иконки упражнений (Тренировки C и D)

Для следующих упражнений иконки **не найдены** в папке `static/images/3/`.
Вместо них временно используется заглушка `placeholder.webp`.

## Тренировка C

| # | Упражнение | trackingType |
|---|---|---|
| 7 | Разведение бедра (Hip Abduction) | weight_reps |

## Тренировка D

| # | Упражнение | trackingType |
|---|---|---|
| 1 | Wall Angels | reps |
| 3 | Ягодичный мостик на скамье (Hip Thrust) | weight_reps |
| 4 | Копенгагенская планка (Copenhagen Plank) | time |
| 6 | Проходка с гантелью (Suitcase Carry) | weight_time |

## Как добавить иконку

1. Поместить файл `.png` или `.webp` в папку `static/images/3/`
2. Открыть `app.py`
3. В словаре `EXERCISES` найти нужное упражнение (тренировка `C` или `D`)
4. Заменить `'/static/images/3/placeholder.webp'` на путь к новому файлу

## Использованные иконки

| Файл | Упражнение |
|---|---|
| `dead-hang.webp` | Вис на турнике (Dead Hang) |
| `cat-cow.webp` | Кошка-корова (Cat-Cow) |
| `hip-90-90.webp` | 90/90 Hip Mobility |
| `hip-flexor-stretch.webp` | Растяжка сгибателей бедра у стены |
| `bird-dog.webp` | Bird Dog |
| `side-plank.webp` | Боковая планка (Side Plank) |
| `back-extension-hold.webp` | Статическое удержание корпуса под 45° |
| `back-extension.webp` | Гиперэкстензия (Back Extension) |
| `thread-needle.webp` | Продевание иглы (Thread the Needle) |
| `placeholder.webp` | Заглушка для 5 упражнений без иконок |
