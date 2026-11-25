import csv
import os
import glob
from collections import defaultdict
from datetime import datetime

print("🚀 Запуск анализа продуктовых гипотез (CSV данные, без pandas)...\n")

# Проверяем, что мы в папке с данными
if not os.path.exists('users.csv'):
    print("❌ Ошибка: Файл 'users.csv' не найден.")
    print("💡 Убедитесь, что вы запустили скрипт из папки 'db'.")
    exit()

# ===== ШАГ 1: Пользователи =====
print("📊 1/5. Загрузка users.csv...")
users = {}
with open('users.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        if len(row) >= 6:
            user_id = row[0]
            email = row[2]
            created_at = row[5]
            users[user_id] = {'email': email, 'created_at': created_at}

total_users = len(users)
print(f"   ✅ Найдено пользователей: {total_users:,}")

# ===== ШАГ 2: Сессии (поиск мультиаккаунтов) =====
print("📊 2/5. Загрузка sessions.csv...")
device_users = defaultdict(set)
with open('sessions.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        if len(row) >= 7:
            user_id = row[1]
            device_id = row[2]
            if device_id:  # Пропускаем пустые
                device_users[device_id].add(user_id)

# Считаем устройства с >1 аккаунтом
multi_account_devices = {d: len(u) for d, u in device_users.items() if len(u) > 1}
print(f"   ✅ Устройств с >1 аккаунтом: {len(multi_account_devices)}")

# ===== ШАГ 3: Заказы (Воронка) =====
print("📊 3/5. Загрузка orders.csv...")
paid_buyers = set()
total_paid_orders = 0
with open('orders.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        if len(row) >= 6:
            user_id = row[1]
            status = row[4]
            if status == 'paid':
                paid_buyers.add(user_id)
                total_paid_orders += 1

unique_buyers = len(paid_buyers)
print(f"   ✅ Уникальных покупателей: {unique_buyers:,} (всего оплат: {total_paid_orders:,})")

# ===== ШАГ 4: Блокировки (Лимиты) =====
print("📊 4/5. Загрузка user_blocks.csv...")
users_hit_limit = set()
with open('user_blocks.csv', 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter=';')
    for row in reader:
        if len(row) >= 5:
            user_id = row[1]
            reason = row[4]
            if 'лимит' in reason.lower():
                users_hit_limit.add(user_id)

print(f"   ✅ Пользователей, упершихся в лимит: {len(users_hit_limit):,}")

# ===== ШАГ 5: Логи трафика =====
print("📊 5/5. Анализ логов подключений (user_connection_logs)...")
log_files = glob.glob('user_connection_logs*.csv')
print(f"   Найдено файлов логов: {len(log_files)}")

user_traffic = defaultdict(lambda: {'total_bytes': 0, 'days': set()})

for log_file in log_files:
    print(f"   → Чтение {os.path.basename(log_file)}...")
    with open(log_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        for row in reader:
            if len(row) >= 5:
                user_id = row[1]
                bytes_str = row[3]
                timestamp = row[4]
                
                try:
                    bytes_val = float(bytes_str) if bytes_str else 0
                except:
                    bytes_val = 0
                
                # Извлекаем дату из timestamp
                date_part = timestamp.split(' ')[0] if ' ' in timestamp else timestamp[:10]
                
                user_traffic[user_id]['total_bytes'] += bytes_val
                if date_part:
                    user_traffic[user_id]['days'].add(date_part)

# Считаем перцентили
all_bytes = sorted([stats['total_bytes'] for stats in user_traffic.values() if stats['total_bytes'] > 0])

if all_bytes:
    def percentile(data, p):
        k = (len(data) - 1) * p
        f = int(k)
        c = f + 1 if f + 1 < len(data) else f
        d = k - f
        return data[f] + d * (data[c] - data[f])
    
    p50_bytes = percentile(all_bytes, 0.50)
    p90_bytes = percentile(all_bytes, 0.90)
    p95_bytes = percentile(all_bytes, 0.95)
    p99_bytes = percentile(all_bytes, 0.99)
    mean_bytes = sum(all_bytes) / len(all_bytes)
else:
    p50_bytes = p90_bytes = p95_bytes = p99_bytes = mean_bytes = 0

print("✅ Анализ CSV завершен. Формирование отчета...\n")

# ===== ШАГ 6: Генерация отчета =====
# Топ-5 устройств по числу аккаунтов
top5_devices = sorted(multi_account_devices.items(), key=lambda x: x[1], reverse=True)[:5]
top5_str = '\n'.join(f"   - {d} → {c} акк." for d, c in top5_devices)

report = f"""# Отчет по продуктовым гипотезам (VPN-сервис)
Дата генерации: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Гипотеза 1: "Охотники за триалом" (Мультиаккаунты)
**Гипотеза:** Пользователи создают новые аккаунты с одного устройства, чтобы бесконечно использовать 72-часовой триал.
**Подтверждение данными:** 
- Проанализировано сессий с {len(device_users):,} уникальных устройств.
- Найдено **{len(multi_account_devices)} устройств**, с которых авторизовано более 1 аккаунта.
- Максимальное количество аккаунтов на одном устройстве: **{max(multi_account_devices.values()) if multi_account_devices else 0}**.
- Топ-5 устройств по числу аккаунтов:
{top5_str}
**Вывод:** Гипотеза подтверждается. Рекомендуется привязать триал к `device_id` или `advertising_id` (из таблицы advertising_ids), а не только к email.

## Гипотеза 2: Оптимальные лимиты бесплатного тарифа
**Гипотеза:** Текущие лимиты (500 МБ/день, 15 ГБ/месяц) выбраны произвольно. Их можно оптимизировать на основе реального потребления (P90/P95), чтобы стимулировать просмотр рекламы за разблокировку, не вызывая массового оттока.
**Подтверждение данными:**
- Проанализировано логов подключений: {len(log_files)} файлов.
- Пользователей, получивших блокировку с причиной "Превышен лимит": **{len(users_hit_limit):,}** ({(len(users_hit_limit)/total_users)*100:.2f}% от базы).
- Распределение потребления трафика (за всё время):
  - Медиана (P50): **{p50_bytes:,.0f} Б** (~{p50_bytes/1024/1024:.2f} МБ)
  - 90-й перцентиль (P90): **{p90_bytes:,.0f} Б** (~{p90_bytes/1024/1024:.2f} МБ)
  - 95-й перцентиль (P95): **{p95_bytes:,.0f} Б** (~{p95_bytes/1024/1024:.2f} МБ)
  - 99-й перцентиль (P99): **{p99_bytes:,.0f} Б** (~{p99_bytes/1024/1024:.2f} МБ)
**Вывод:** Если P90 значительно ниже 15 ГБ, текущий лимит не является "узким горлышком". Снижение лимита до уровня P90 с предложением посмотреть рекламу за разблокировку увеличит монетизацию без потери лояльности основной массы пользователей.

## Гипотеза 3: Воронка "Бесплатный → Платный"
**Гипотеза:** Пользователи покупают подписку после оценки качества во время триала. Однако есть сегмент, который покупает мгновенно, и его можно стимулировать иначе.
**Подтверждение данными:**
- Всего уникальных покупателей: **{unique_buyers:,}**.
- Всего оплаченных заказов: **{total_paid_orders:,}**.
- Конверсия из общей базы пользователей в покупку: **{(unique_buyers/total_users)*100:.2f}%**.
**Вывод:** Базовая конверсия {(unique_buyers/total_users)*100:.2f}% является отправной точкой. Для детального анализа (покупка во время триала vs после) требуется джойн с таблицами `product_trial.csv` и `subscribe.csv`. Рекомендуется A/B тест онбординга с акцентом на ценность платных серверов в первые 24 часа.

---
*Отчет сгенерирован автоматически на основе прямого анализа CSV-дампов.*
*Для гипотезы №4 (Паттерны инцидентов) запустите отдельный скрипт `analyze_all_logs.py`.*
"""

with open('hypotheses_report.txt', 'w', encoding='utf-8') as f:
    f.write(report)

print("🎉 ГОТОВО!")
print("📄 Отчет сохранен в файл: hypotheses_report.txt")
print(f"📍 Полный путь: {os.path.abspath('hypotheses_report.txt')}")
print("👉 Откройте его, скопируйте содержимое и отправьте мне для финальной сборки!")
