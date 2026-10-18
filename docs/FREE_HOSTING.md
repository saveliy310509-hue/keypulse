# Бесплатный хостинг 24/7 для KeyPulse

Задача: бот должен отвечать круглосуточно, без засыпаний и с сохранением базы.
Проверено на октябрь 2026.

## Короткий вывод

**Единственный по-настоящему бесплатный вариант «24/7 без перебоев» — своя микро-VM в бесплатном облаке.** Любой PaaS с «free» либо засыпает, либо кончается через неделю.

| Вариант | 24/7 | База сохраняется | Плата | Реальность |
|---|---|---|---|---|
| **GCP e2-micro (Always Free)** ✅ | да | да (диск 30 ГБ) | $0 | 1 VM в `us-central1` / `us-west1` / `us-east1`, карта для верификации |
| **Oracle Cloud Always Free** ✅ | да | да (200 ГБ) | $0 | 2 OCPU / 12 ГБ ARM, но простой VM могут отозвать |
| Fly.io | да | да (volume) | платно | бесплатные allowance для новых аккаунтов закрыты |
| Render Free | ❌ | ❌ | $0 | засыпает через 15 мин, диск недоступен |
| Railway | ❌ | да | trial $5, потом $5/мес | халява заканчивается |
| PythonAnywhere Free | ❌ | да | $0 | нет always-on задач для ботов |

---

## Вариант 1: Google Cloud e2-micro (рекомендую)

Почему: **не засыпает, не отзывается за простой**, диск постоянный, 1 ГБ RAM хватает с запасом (бот занимает ~120 МБ).

### Шаги

1. Открой [console.cloud.google.com](https://console.cloud.google.com/) → активируй Free Trial ($300 на 90 дней, карта нужна только для верификации, списаний нет).
2. **Compute Engine → Create instance**:
   - Name: `keypulse`
   - Region: `us-central1` (или `us-west1`, `us-east1` — только там действует Always Free)
   - Machine type: **e2-micro**
   - Boot disk: **Debian 12**, 30 GB standard
   - Firewall: HTTP/HTTPS можно не включать
3. В блоке **Advanced → Management → Metadata** добавь:

   | Ключ | Значение |
   |---|---|
   | `startup-script` | содержимое `deploy/gcp-startup.sh` |
   | `REPO_URL` | ссылка на твой репозиторий с KeyPulse |
   | `BOT_TOKEN` | токен от @BotFather |
   | `ADMIN_ID` | `8554520733` |
   | `API_SECRET` | длинная случайная строка |

   Либо одной командой в Cloud Shell:

   ```bash
   gcloud compute instances create keypulse \
     --zone=us-central1-a \
     --machine-type=e2-micro \
     --image-family=debian-12 \
     --image-project=debian-cloud \
     --metadata=REPO_URL=https://github.com/USER/keypulse.git,BOT_TOKEN=8974...,ADMIN_ID=8554520733,API_SECRET=xxx \
     --metadata-from-file=startup-script=deploy/gcp-startup.sh
   ```

4. Через 2–3 минуты проверь:

   ```bash
   gcloud compute ssh keypulse --zone=us-central1-a
   sudo systemctl status keypulse
   curl http://127.0.0.1:8080/health
   ```

5. Напиши боту `/start` — должен ответить.

### Обновление кода

```bash
cd /opt/keypulse && sudo git pull
sudo .venv/bin/pip install -r requirements.txt
sudo systemctl restart keypulse
```

### Если нужен HWID API снаружи

По умолчанию порт 8080 закрыт файрволом GCP — это хорошо. Открывай только если плагин ходит напрямую:

```bash
gcloud compute firewall-rules create keypulse-api \
  --allow tcp:8080 --target-tags=keypulse --source-ranges=0.0.0.0/0
```

Лучше — не открывать порт, а поднять **Cloudflare Tunnel** (бесплатно, HTTPS из коробки):

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
sudo install cloudflared /usr/local/bin/ && rm cloudflared
cloudflared tunnel login
cloudflared tunnel create keypulse
cloudflared tunnel route dns keypulse api.твойдомен.com
cloudflared tunnel run --url http://127.0.0.1:8080 keypulse
```

---

## Вариант 2: Oracle Cloud Always Free

Даёт заметно больше железа (2 OCPU / 12 ГБ ARM, 200 ГБ диска), но есть подвох.

### Подвох: реклейм простаивающих машин

Oracle отзывает Always Free инстансы, если за 7 дней одновременно:

- 95-й перцентиль CPU < 20%
- сеть < 20%
- память < 20% (только для ARM)

Телеграм-бот как раз почти не грузит железо — риск реальный.

**Решения:**
1. **Апгрейд на Pay As You Go** — Always Free ресурсы остаются $0, но политика реклейма к тебе не применяется. Самый надёжный путь.
2. Взять **AMD micro** (2× 1/8 OCPU, 1 ГБ) — метрика памяти к ним не применяется.
3. Держать на VM что-то ещё (Uptime Kuma, панель, cron-задачи), чтобы машина не считалась простаивающей.

Ещё нюансы: домашний регион выбирается навсегда; ARM-ёмкость в популярных регионах часто «out of host capacity»; регистрация иногда отклоняется антифродом без объяснений.

### Шаги

1. [cloud.oracle.com](https://cloud.oracle.com/) → Always Free аккаунт.
2. **Compute → Instances → Create**:
   - Shape: `VM.Standard.A1.Flex`, 2 OCPU / 12 ГБ (или `VM.Standard.E2.1.Micro`)
   - Image: **Ubuntu 22.04** (важно — скрипт под apt)
   - Загрузи SSH-ключ, скачай приватный ключ.
3. Открой порты в **Networking → VCN → Security Lists → Default Security List**: добавь ingress TCP 8080 (если нужен API).
4. На самой VM разреши порт в iptables (образы Oracle блокируют всё):

   ```bash
   sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8080 -j ACCEPT
   sudo netfilter-persistent save
   ```

5. Залей проект и запусти установку:

   ```bash
   scp -r ./KeyPulse ubuntu@<IP>:/tmp/keypulse
   ssh ubuntu@<IP>
   sudo mkdir -p /opt/keypulse && sudo cp -r /tmp/keypulse/* /opt/keypulse/
   sudo bash /opt/keypulse/deploy/install.sh
   sudo nano /opt/keypulse/.env     # вписать BOT_TOKEN, ADMIN_ID, API_SECRET
   sudo systemctl start keypulse
   ```

6. Проверь: `sudo systemctl status keypulse`

---

## После установки (оба варианта)

```bash
# статус и логи
sudo systemctl status keypulse
sudo journalctl -u keypulse -f

# автозапуск уже включён, перезапуск при падении — Restart=always
```

### Бэкап базы

```bash
sudo cp /opt/keypulse/deploy/backup.sh /opt/keypulse/backup.sh
sudo chmod +x /opt/keypulse/backup.sh
sudo crontab -e
# добавь строку:
0 4 * * * /opt/keypulse/backup.sh >> /var/log/keypulse-backup.log 2>&1
```

Бэкапы складываются в `/opt/keypulse/backups`, хранятся 14 дней.

### Мониторинг бесплатно

- [UptimeRobot](https://uptimerobot.com/) — пингует `http://<IP>:8080/health` каждые 5 минут и присылает в Telegram, если упало.
- Или `systemd` + `journalctl` — но о падении узнаешь только когда заглянешь.

---

## Вариант 3: свой ПК с Windows (бесплатно прямо сейчас)

Если карты для облака нет — бот может жить на твоём компьютере как фоновая задача.
Ограничение одно: ПК должен быть включён.

```powershell
# PowerShell от администратора
powershell -ExecutionPolicy Bypass -File .\deploy\install_windows.ps1
```

Скрипт создаёт venv, ставит зависимости и регистрирует задачу `KeyPulseBot`:

- автозапуск при входе в Windows;
- **автоперезапуск каждую минуту после падения** (999 попыток);
- запуск скрыто, без окна консоли (`deploy/start_hidden.vbs`);
- логи в `logs\bot.log` и `logs\bot.err.log`.

Чтобы ПК не засыпал:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

Проверить, что работает:

```powershell
Get-ScheduledTask -TaskName KeyPulseBot | Get-ScheduledTaskInfo
Get-Content .\logs\bot.log -Tail 20
```

Остановить / запустить:

```powershell
Stop-ScheduledTask -TaskName KeyPulseBot
Start-ScheduledTask -TaskName KeyPulseBot
```

Удалить задачу: `Unregister-ScheduledTask -TaskName KeyPulseBot -Confirm:$false`

---

## Проверка, что хостинг действительно 24/7

1. `systemctl is-enabled keypulse` → `enabled`
2. Перезагрузи VM: `sudo reboot` → через минуту бот снова отвечает.
3. Урони процесс: `sudo pkill -f main.py` → systemd поднимет за 5 секунд.
4. Через сутки проверь `uptime` и `sudo journalctl -u keypulse | grep -c "Бот @"`.

---

## Если карты нет вообще

Тогда бесплатного 24/7 не будет — все нормальные free tier требуют карту для верификации. Варианты:

- запуск на своём ПК с автозапуском (`run.bat` в автозагрузке) — бесплатно, но пока ПК включён;
- дешёвый VPS за $2–3/мес (Hetzner, Aeza, Timeweb) — надёжнее любого free tier;
- попросить карту у знакомых для верификации GCP/Oracle.
