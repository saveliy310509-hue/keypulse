# HWID API — подключение из приложения и Minecraft-плагина

Сервер поднимается вместе с ботом (`python main.py`) на `API_HOST:API_PORT` (по умолчанию `0.0.0.0:8080`).
Можно запустить отдельно:

```bash
python -m uvicorn bot.hwid_api:app --host 0.0.0.0 --port 8080
```

Все запросы требуют заголовок:

```
X-Api-Secret: <API_SECRET>
```

---

## Эндпоинты

### POST /api/activate

Первый запуск приложения: привязывает ключ к железу.

```json
{"key": "KP-7F3A-9K2M-QW4Z", "hwid": "AA-BB-CC-DD-EE-FF"}
```

| Ответ | Когда |
|---|---|
| `{"ok": true, "message": "Ключ успешно активирован!", "expires_at": "...", "days": 30}` | ключ был свободен |
| `{"ok": true, "message": "Ключ уже активирован на этом устройстве"}` | тот же HWID |
| `{"ok": false, "message": "Ключ уже активирован на другом устройстве..."}` | чужой HWID |
| `{"ok": false, "message": "Срок действия ключа истёк"}` | просрочен |
| `{"ok": false, "message": "Ключ не найден"}` | нет такого |

### POST /api/verify

Проверка при каждом запуске (без записи в БД).

```json
{"key": "KP-7F3A-9K2M-QW4Z", "hwid": "AA-BB-CC-DD-EE-FF"}
```

`{"ok": true, "message": "Ключ валиден", "days": 30}` — можно работать.
`{"ok": false, "message": "HWID не совпадает"}` — ключ утёк на другое устройство.

### POST /api/reset-hwid

Снимает привязку. Бот вызывает это после оплаты сброса, но можно и вручную.

### GET /api/key/{key}

Полная информация: дни, метка, статус, HWID, срок, владелец.

```bash
curl http://localhost:8080/api/key/KP-7F3A-9K2M-QW4Z -H "X-Api-Secret: <API_SECRET>"
```

---

## Как получить HWID

HWID должен быть стабильным идентификатором машины. Варианты:

**Windows (PowerShell / C#)**
```powershell
(Get-CimInstance Win32_ComputerSystemProduct).UUID
```

**Java (Minecraft-плагин)**
```java
String hwid = UUID.nameUUIDFromBytes(
    (System.getProperty("os.name") + System.getProperty("os.arch")
     + Runtime.getRuntime().availableProcessors()).getBytes()
).toString();
```
⚠️ Такой HWID вычисляется на сервере, а не на клиенте — для плагина лучше присылать HWID с клиента через мод/лаунчер, иначе он будет одинаковым для всех игроков, зашедших на один сервер.

**Python**
```python
import uuid, platform, hashlib
raw = f"{platform.node()}-{platform.machine()}-{uuid.getnode()}"
hwid = hashlib.sha256(raw.encode()).hexdigest()[:16]
```

---

## Пример: Java-клиент (OkHttp)

```java
import okhttp3.*;

public class KeyPulseClient {
    private static final String BASE = "http://127.0.0.1:8080";
    private static final String SECRET = "<API_SECRET>";
    private static final MediaType JSON = MediaType.get("application/json");

    public static boolean activate(String key, String hwid) throws Exception {
        OkHttpClient c = new OkHttpClient();
        String body = "{\"key\":\"" + key + "\",\"hwid\":\"" + hwid + "\"}";
        Request req = new Request.Builder()
                .url(BASE + "/api/activate")
                .header("X-Api-Secret", SECRET)
                .post(RequestBody.create(body, JSON))
                .build();
        try (Response r = c.newCall(req).execute()) {
            String s = r.body().string();
            return s.contains("\"ok\":true");
        }
    }
}
```

Вызывай `activate` при первом входе игрока и `verify` при каждом следующем. Если `ok:false` — кикай с сообщением из `message`.

---

## Пример: обёртка на Python

```python
import requests

API = "http://127.0.0.1:8080"
H = {"X-Api-Secret": "<API_SECRET>"}

def check(key: str, hwid: str) -> bool:
    r = requests.post(f"{API}/api/verify", json={"key": key, "hwid": hwid}, headers=H, timeout=10)
    data = r.json()
    if not data["ok"]:
        print("Отказ:", data["message"])
    return data["ok"]
```

---

## Безопасность

- API слушает `0.0.0.0` — если клиенты не подключаются извне, поставь `API_HOST=127.0.0.1`.
- Смени `API_SECRET` перед релизом.
- Ставь HTTPS (nginx/Caddy reverse-proxy) — иначе секрет уйдёт открытым текстом.
- Не отдавай `API_SECRET` в клиентское приложение, которое распространяется публично: лучше прокси-эндпоинт на своём сервере без секрета.
