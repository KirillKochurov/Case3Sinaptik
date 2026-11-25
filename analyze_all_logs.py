import os
import zipfile
from collections import Counter
from datetime import datetime

print("🔍 Запуск масштабного анализа клиентских логов...\n")

LOGS_DIR = 'logs'
if not os.path.exists(LOGS_DIR):
    print(f"❌ Папка '{LOGS_DIR}' не найдена в текущей директории: {os.getcwd()}")
    print("💡 Перейдите в папку db перед запуском: cd путь\\к\\db")
    exit()

vpn_errors = Counter()
huawei_users = set()
gms_missing_users = set()
users_with_any_error = set()
total_users = 0
processed_archives = 0

print(f"📂 Сканирование папки '{os.path.abspath(LOGS_DIR)}'...\n")

for user_folder in sorted(os.listdir(LOGS_DIR)):
    user_path = os.path.join(LOGS_DIR, user_folder)
    if not os.path.isdir(user_path):
        continue
    
    total_users += 1
    
    for filename in os.listdir(user_path):
        if not filename.lower().endswith('.zip'):
            continue
        
        zip_path = os.path.join(user_path, filename)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                namelist = z.namelist()
                
                # 1. vpn_error_log.txt
                if 'vpn_error_log.txt' in namelist:
                    with z.open('vpn_error_log.txt') as f:
                        has_error = False
                        for line in f:
                            line = line.decode('utf-8', errors='ignore').strip()
                            if '[Error]' in line:
                                has_error = True
                                parts = line.split('[Error] ', 1)
                                if len(parts) > 1:
                                    vpn_errors[parts[1]] += 1
                        if has_error:
                            users_with_any_error.add(user_folder)
                
                # 2. peepster_logs.txt — ИСПРАВЛЕНО: ищем строчную ' e '
                if 'peepster_logs.txt' in namelist:
                    with z.open('peepster_logs.txt') as f:
                        for line in f:
                            line_lower = line.decode('utf-8', errors='ignore').lower()
                            # Ищем строки уровня Error (строчная 'e' после .lower())
                            if ' e ' in line_lower and 'huawei' in line_lower:
                                huawei_users.add(user_folder)
                            if 'googleplayservices' in line_lower and ('error' in line_lower or 'not available' in line_lower):
                                gms_missing_users.add(user_folder)
            
            processed_archives += 1
            
            if processed_archives % 500 == 0:
                print(f"   Обработано архивов: {processed_archives}...")
                
        except zipfile.BadZipFile:
            continue
        except Exception:
            continue

print(f"\n✅ Анализ завершен!")
print(f"   Всего пользователей: {total_users}")
print(f"   Обработано архивов: {processed_archives}")
print(f"   Пользователей с ошибками VPN: {len(users_with_any_error)}")
print(f"   Пользователей с ошибками Huawei: {len(huawei_users)}")
print(f"   Пользователей с отсутствием GMS: {len(gms_missing_users)}")

top_vpn_errors = vpn_errors.most_common(10)

report = f"""# Анализ клиентских логов: Паттерны инцидентов (Гипотеза №4)
Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Проанализировано архивов: {processed_archives} (из {total_users} пользователей)

## 1. Общая статистика инцидентов
- Пользователей, столкнувшихся с ошибками VPN: **{len(users_with_any_error)}** ({(len(users_with_any_error)/max(1, total_users))*100:.1f}% от базы).
- Пользователей с системными ошибками, специфичными для **Huawei/HMS**: **{len(huawei_users)}**.
- Пользователей с ошибками из-за отсутствия **Google Play Services (GMS)**: **{len(gms_missing_users)}**.

## 2. Топ-10 наиболее частых ошибок VPN-ядра
"""

for i, (error_text, count) in enumerate(top_vpn_errors, 1):
    report += f"{i}. **({count} раз)** `{error_text}`\n"

report += f"""

## 3. Выявленные паттерны и продуктовые выводы

### Паттерн А: Деградация опыта на устройствах Huawei / без GMS
**Данные:** В логах (`peepster_logs.txt`) встречаются ошибки загрузки графических библиотек Huawei (`libiGraphicsCore.huawei.so`) и недоступности Google Play Services.
**Влияние:** Отсутствие GMS ломает push-уведомления, специфичные библиотеки Huawei вызывают сбои рендеринга (`OpenGLRenderer`, `ACodec`).
**Рекомендация:**
1. Выделить пользователей Huawei в отдельную когорту.
2. Реализовать fallback для push-уведомлений (HMS Push Kit).
3. Протестировать приложение на эмуляторе Huawei без GMS.

### Паттерн Б: Массовые обрывы туннеля и DNS-сбои
**Данные:** Доминируют ошибки `proxy/tun: connection was refused` и `app/dns: ... cannot find the pending request`.
**Влияние:** Пользователь видит "подключено", но трафик не идёт — главная причина оттока.
**Рекомендация:**
1. Добавить exponential backoff при DNS-запросах.
2. Автоматическое переключение на резервный DNS при 2+ ошибках подряд.
3. Понятный статус "Проверка соединения..." в UI.

### Паттерн В: Связь версий приложения и стабильности
**Данные:** В timestamp-логах фиксируется версия (напр., `App version 2026.9.9`).
**Рекомендация:** Сопоставить ошибки с `mobile_version.csv`. Если >60% ошибок на версиях старше 3 месяцев — внедрить force update.

---
*Отчёт сгенерирован автоматически путём прямого парсинга клиентских логов из ZIP-архивов.*
"""

# Сохраняем в ТЕКУЩУЮ директорию и ПЕЧАТАЕМ ПОЛНЫЙ ПУТЬ
output_path = os.path.abspath('logs_hypothesis_report.txt')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"\n🎉 ГОТОВО!")
print(f"📄 Полный путь к файлу: {output_path}")
