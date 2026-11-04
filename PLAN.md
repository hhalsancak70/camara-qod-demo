# QoD × GCC Demo — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raspberry Pi 5 üzerinde, CAMARA QoD API'sinin video akışına gerçek etkisini ve P2 (habersiz gönderici) ile P3 (haberdar gönderici) farkını tarayıcıdan canlı gösteren demo.

**Architecture:** Tüm demo tek bir Docker konteynerinde çalışır; Mac'te geliştirilir, Pi'de aynı komutla açılır. Konteyner içinde üç network namespace (`edge`, `others`, `net`) mobil ağı emüle eder. `net` içindeki `tc` HTB darboğazına QoD servisi öncelik sınıfı ekler. aiortc ile gönderilen video, kök namespace'teki alıcıya gider. Aynı süreçteki orkestratör CAMARA API'sini HTTP ile çağırır ve panel tarayıcıya canlı veri gönderir.

**Tech Stack:** Python 3.13, aiortc 1.15 (av < 18), aiohttp, iproute2 (`ip`, `tc`), iperf3, pytest, Debian trixie arm64 Docker imajı, Chart.js (yerel dosya).

**Spec:** `/Users/alsancak/Downloads/bitirme/demo/TASARIM.md`

## Global Constraints

- Kod yeri: `~/Downloads/bitirme/demo/` (yerel git deposu; uzağa push yok).
- Her şey arm64'te çalışmalı (Mac Apple Silicon ve Raspberry Pi 5).
- İnternetsiz çalışma: Chart.js dahil tüm web dosyaları depoda; CDN yok.
- Darboğaz 3000 kbit/s; RTT ~50 ms; QoD oturumu varsayılan 30 sn; etkinleşme gecikmesi varsayılan 1 sn; P3 ön düşüş Δ = 4 sn.
- Profiller: `QOS_VIDEO_M` = 1500 kbps, `QOS_VIDEO_L` = 2500 kbps (senaryo `QOS_VIDEO_L` kullanır).
- QoD API yol önekleri: `/quality-on-demand/v1` ve `/qos-profiles/v1`, port 9091. Panel/uygulama portu 8080.
- Video: H.264, 640×360, 30 fps. aiortc H.264 kodlayıcı üst sınırı 3 Mbps'e (varsayılan) dokunulmaz; profil 2,5 Mbps altında kalır.
- Arayüz metni Türkçe. Alt bilgi metni birebir: "Ağ: Raspberry Pi üzerinde emüle edilmiş 3 Mbps mobil uplink (Linux tc). QoD API: CAMARA QoD 1.1.0 uyumlu yerel servis."
- Laboratuvar sapmaları (README'de yazılı olacak): sabit bearer token `demo-token`, `http` sink kabul.
- Etki taklit edilmez: video yalnızca gerçek `tc` darboğazından geçer.

## Adres planı (tüm görevlerde aynı)

| Namespace | Arayüz | IP | Karşısı |
|---|---|---|---|
| `edge` | `e0` | 10.10.1.2/24 | `net:n-edge` 10.10.1.1 |
| `others` | `o0` | 10.10.3.2/24 | `net:n-oth` 10.10.3.1 |
| `net` | `n-srv` | 10.10.2.1/24 | kök `s0` |
| kök | `s0` | 10.10.2.2/24 (video sunucusu) + 10.10.2.3/24 (yük hedefi) | |

Darboğaz: `net` içindeki `n-srv` çıkışı (uplink). RTT: `net` içinde `n-edge` ve `n-oth` çıkışında `netem delay 50ms` (yalnızca dönüş yolu).

## Review Focus

- QoD açıkken demo yeniden başlatılırsa eski `tc` sınıfı kalabilir → kurulum betiği her başlangıçta qdisc'leri silip baştan kurmalı. (Görev 2 testi)
- Aynı cihaza ikinci QoD isteği → `409 CONFLICT`, panelde hata olarak görünmeli, çökmemeli. (Görev 3 testi)
- Oturum süresi dolmadan elle silinirse → `tc` sınıfı hemen kalkmalı, durum `UNAVAILABLE / DELETE_REQUESTED`. (Görev 3 testi)
- Video hiç profil hızına ulaşamazsa → "ulaşamadı" ve ulaşılan en yüksek değer gösterilmeli, `None` bölme hatası olmamalı. (Görev 5 testi)
- Senaryo çalışırken ikinci senaryo düğmesine basılırsa → ikinci istek reddedilmeli ("senaryo zaten çalışıyor"). (Görev 5 testi)

---

## Dosya yapısı

```
demo/
  Dockerfile, docker-compose.yml, Makefile, README.md, requirements.txt
  net/setup.sh, net/teardown.sh, net/smoke.sh        # namespace + tc
  qod/profiles.py      # profil tablosu
  qod/sessions.py      # oturum durum makinesi (saf mantık)
  qod/shaper.py        # tc komutları (TcShaper, FakeShaper)
  qod/server.py        # aiohttp CAMARA uç noktaları + bildirim gönderimi
  media/source.py      # sentetik kare üretici (zaman damgalı)
  media/sender.py      # edge'de çalışan aiortc gönderici
  app/receiver.py      # aiortc alıcı + ölçüm + P3 kancası
  app/metrics.py       # ölçüm fonksiyonları (saf)
  app/orchestrator.py  # QoD istemcisi, sink, P2/P3, senaryo
  app/web.py           # panel: HTTP, WebSocket, MJPEG
  app/static/index.html, app/static/app.js, app/static/chart.umd.min.js
  run.sh               # her şeyi başlatır
  tests/               # pytest
  runs/                # koşu kayıtları (git dışı)
```

---

### Task 1: Ortam — Docker konteynerinde netns ve HTB çalışıyor mu

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `requirements.txt`, `Makefile`, `.gitignore`

**Interfaces:**
- Produces: `make shell` (konteynerde kabuk), `make up` (demo), konteyner `--privileged`, `network_mode: host`, `/demo` bağlı klasör.

- [ ] **Step 1:** `git init` (demo klasöründe), `.gitignore` → `runs/`, `__pycache__/`, `.venv/`.
- [ ] **Step 2:** `Dockerfile`: `FROM debian:trixie-slim`; apt: `python3 python3-venv iproute2 iperf3 procps`; venv'e `requirements.txt` (`aiortc==1.15.0`, `aiohttp`, `pytest`, `pytest-asyncio`, `numpy`, `pillow`).
- [ ] **Step 3:** `docker-compose.yml`: servis `demo`, `privileged: true`, `network_mode: host`, `volumes: [".:/demo"]`, `command: /demo/run.sh`.
- [ ] **Step 4: Doğrulama:** `make shell` içinde
  `ip netns add t && ip netns exec t ip link add d type dummy && ip netns exec t ip link set d up && ip netns exec t tc qdisc add dev d root handle 1: htb default 20 && echo HTB_OK`
  Beklenen: `HTB_OK`. **HTB yoksa:** Docker Desktop yerine UTM'de Debian 13 arm64 VM kur, aynı Docker'ı orada çalıştır; plan değişmez.
- [ ] **Step 5:** `python -c "import aiortc, av; print(av.codec.Codec('libx264','w').name)"` → `libx264`.
- [ ] **Step 6: Commit** `chore: docker ortamı`

### Task 2: Ağ topolojisi ve darboğaz

**Files:**
- Create: `net/setup.sh`, `net/teardown.sh`, `net/smoke.sh`

**Interfaces:**
- Produces: Adres planındaki namespace'ler; `net` içinde `n-srv` üzerinde `htb` kök `1:`, sınıf `1:1` (3000kbit), varsayılan sınıf `1:20` (rate 3000kbit, ceil 3000kbit, yaprak `pfifo limit 400`). `ip netns exec edge|others|net ...` ile erişim.

- [ ] **Step 1:** `teardown.sh`: namespace'leri ve `s0`'ı varsa siler (hata vermeden).
- [ ] **Step 2:** `setup.sh`: önce `teardown.sh`; namespace'ler, veth çiftleri, IP'ler, `net` içinde `ip_forward=1`, `edge`/`others` varsayılan rota → `net`, kökte 10.10.1.0/24 ve 10.10.3.0/24 rotaları → 10.10.2.1; HTB ve netem yukarıdaki gibi.
- [ ] **Step 3:** `smoke.sh`:
  - `ip netns exec edge ping -c 5 10.10.2.2` → ortalama RTT 45–60 ms.
  - Kökte `iperf3 -s -B 10.10.2.3 -D`; `ip netns exec others iperf3 -c 10.10.2.3 -t 5` → alıcı tarafı 2,6–3,1 Mbit/s.
  - Betik her iki koşulu kontrol edip `SMOKE_OK` yazar, değilse çıkış kodu 1.
- [ ] **Step 4:** `setup.sh && smoke.sh` → `SMOKE_OK`. `setup.sh`'ı iki kez üst üste çalıştırıp yine `SMOKE_OK` (Review Focus 1).
- [ ] **Step 5: Commit** `feat: emüle mobil ağ ve darboğaz`

### Task 3: CAMARA QoD servisi

**Files:**
- Create: `qod/profiles.py`, `qod/sessions.py`, `qod/shaper.py`, `qod/server.py`
- Test: `tests/test_sessions.py`, `tests/test_server.py`

**Interfaces:**
- Produces:
  - `PROFILES: dict[str, Profile]`; `Profile(name, target_kbps:int, min_duration_s:int=5, max_duration_s:int=3600)`
  - `class Shaper(Protocol): add_priority(key:str, device_ip:str, server_ip:str, rate_kbps:int)->None; remove_priority(key:str)->None`
  - `TcShaper(ns="net", dev="n-srv", link_kbps=3000)`: öncelik sınıfı `1:10` (rate=profil, ceil=3000, `prio 0`, yaprak `pfifo limit 50`), `u32 match ip src <device> match ip dst <server> flowid 1:10`; eklerken `1:20` rate'ini `3000 - profil`'e çeker, kaldırınca 3000'e döndürür. `FakeShaper` çağrıları listede tutar.
  - `SessionStore(shaper, clock, activation_delay_s=1.0)` : `create(body:dict)->dict`, `get(id)->dict`, `delete(id)->None`, `extend(id, add_s:int)->dict`, `by_device(ip)->list[dict]`, `tick(now)` (REQUESTED→AVAILABLE, süre dolumu); durum değişince `on_change(session:dict)` geri çağrısı.
  - `make_app(store, token="demo-token") -> aiohttp.web.Application`; HTTP sunucu `python -m qod.server --port 9091`.
  - Bildirim: `sink`'e `POST`, gövde CloudEvent `{"id","source":"qod-demo","specversion":"1.0","type":"org.camaraproject.quality-on-demand.v1.qos-status-changed","time","datacontenttype":"application/json","data":{"sessionId","qosStatus","statusInfo"?}}`.

- [ ] **Step 1: Failing testler (`tests/test_sessions.py`, FakeShaper + sahte saat):**
  - `test_create_is_requested_then_available`: create → `qosStatus=="REQUESTED"`, shaper boş; `tick(+1.0)` → `AVAILABLE`, `startedAt` var, `expiresAt == startedAt+30s`, shaper'da `add_priority(...,2500)`.
  - `test_expiry`: `tick(+31)` → `UNAVAILABLE`, `statusInfo=="DURATION_EXPIRED"`, `remove_priority` çağrıldı.
  - `test_delete_removes_priority_immediately`: AVAILABLE iken delete → `remove_priority`, durum `DELETE_REQUESTED` bildirimi (Review Focus 3).
  - `test_second_session_same_device_conflict`: ikinci create → `ConflictError` (Review Focus 2).
  - `test_duration_out_of_range`: `duration=2` → `DurationOutOfRange`.
  - `test_extend_capped_by_max_duration`.
- [ ] **Step 2:** `pytest tests/test_sessions.py` → FAIL.
- [ ] **Step 3:** `profiles.py`, `shaper.py`, `sessions.py`'ı yaz.
- [ ] **Step 4: Failing testler (`tests/test_server.py`, aiohttp test client):** POST `/quality-on-demand/v1/sessions` → `201` + `sessionId`; aynı cihaz tekrar → `409` gövde `{"status":409,"code":"CONFLICT"}`; token yok → `401 UNAUTHENTICATED`; `device` yok → `422 MISSING_IDENTIFIER`; GET bilinmeyen id → `404 NOT_FOUND`; DELETE → `204`; `POST /qos-profiles/v1/retrieve-qos-profiles` → iki profil, `maxUpstreamRate {"value":2500,"unit":"kbps"}`.
- [ ] **Step 5:** `server.py`'ı yaz (arka planda 200 ms'de bir `tick`; bildirim gönderimi hata verirse kaydet, çökme).
- [ ] **Step 6:** `pytest` → tümü PASS. Konteynerde gerçek `TcShaper` ile elle: oturum aç → `ip netns exec net tc class show dev n-srv` içinde `1:10` görünür; sil → kaybolur.
- [ ] **Step 7: Commit** `feat: CAMARA QoD 1.1.0 yerel servis`

### Task 4: Video gönderici ve alıcı

**Files:**
- Create: `media/source.py`, `media/sender.py`, `app/receiver.py`
- Test: `tests/test_source.py`

**Interfaces:**
- Produces:
  - `SyntheticTrack(width=640, height=360, fps=30)` (aiortc `VideoStreamTrack`): hareketli desen; her karenin sol üstüne 64 bitlik gönderim zamanı (ms, `time.time()`) siyah/beyaz bloklarla kodlanır. `decode_stamp(frame: av.VideoFrame) -> int|None`.
  - `python -m media.sender --server http://10.10.2.2:8080/offer` (edge namespace'inde çalışır; H.264'ü tercih eder).
  - `Receiver` (kökte): `POST /offer` işleyicisi, `latest_jpeg() -> bytes|None`, `stats() -> dict{"rx_kbps","e2e_ms","fps","loss_pct","remb_kbps"}` (1 sn pencere), `set_gcc_estimate(kbps:int) -> None` (P3 kancası).
  - P3 kancası: alıcının `RTCRtpReceiver` nesnesindeki `RemoteBitrateEstimator`'a erişip `rate_control.set_estimate(kbps*1000, now_ms)` çağırır. aiortc'de bu alanlar özeldir (`_RTCRtpReceiver__remote_bitrate_estimator`); erişim tek bir yardımcı fonksiyonda toplanır ve aiortc sürümü 1.15.0'a sabitlenir.
- [ ] **Step 1: Failing test:** `test_stamp_roundtrip`: `SyntheticTrack` karesi → `decode_stamp` aynı ms'yi verir (±0); H.264 kodla-çöz sonrası ±0 (bloklar 8×8 piksel, kayıpsız okunur).
- [ ] **Step 2:** FAIL → `source.py` yaz → PASS.
- [ ] **Step 3:** `sender.py` ve `receiver.py`'ı yaz (sinyalleşme aiortc `server` örneği gibi tek HTTP offer/answer).
- [ ] **Step 4: Doğrulama (konteyner, ağ kurulu):** Alıcıyı başlat, `ip netns exec edge python -m media.sender ...`. 20 sn sonra `stats()` → `rx_kbps` 300–3000 arası, `e2e_ms` < 300, `fps` > 20.
- [ ] **Step 5: Doğrulama:** `others`'tan `iperf3 -t 20` başlat → 10 sn içinde `e2e_ms` > 400 veya `rx_kbps` belirgin düşer (tıkanıklık görünüyor).
- [ ] **Step 6: Commit** `feat: aiortc video gönderici ve alıcı`

### Task 5: Orkestratör, ölçümler ve senaryo

**Files:**
- Create: `app/metrics.py`, `app/orchestrator.py`
- Test: `tests/test_metrics.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `Receiver.stats()`, `Receiver.set_gcc_estimate(kbps)` (Task 4); QoD HTTP API (Task 3).
- Produces:
  - `time_to_target(samples:list[tuple[float,float]], t_avail:float, target_kbps:int, frac=0.9) -> float|None`
  - `priority_utilization(samples, t_start:float, t_end:float, target_kbps:int) -> float` (0–1)
  - `closing_spike(samples_e2e:list[tuple[float,float]], t_end:float, window_s=5.0) -> float`
  - `Orchestrator(qod_url, receiver, events)`: `request_qod(profile="QOS_VIDEO_L", duration=30)`, `delete_qod()`, `set_policy("P2"|"P3")`, `start_load()/stop_load()` (others'tan iperf3), `run_scenario(policy) -> RunResult`; sink uç noktası `POST /notifications`; her olay `events.publish(dict)` ile panele.
  - `RunResult(policy, t_to_target_s:float|None, max_kbps:float, utilization:float, closing_spike_ms:float)`; `runs/<zaman>-<policy>.json` dosyasına yazılır (örnekler + API kaydı dahil).
  - Senaryo zaman çizelgesi: 0 sn başla → 10 sn yük → 20 sn QoD iste (30 sn) → bitiş + 14 sn'de yükü durdur → sonuç. P3: `AVAILABLE`'da `set_gcc_estimate(2500)`; `expiresAt − 4 sn`'de `set_gcc_estimate(<QoD öncesi son 5 sn ortalama rx_kbps>)`.
- [ ] **Step 1: Failing testler (`test_metrics.py`):**
  - `time_to_target([(0,500),(5,1500),(10,2300)], 0, 2500)` → `10.0`.
  - Hiç ulaşmayan seri → `None` (Review Focus 4).
  - `priority_utilization` sabit 1250 kbps, hedef 2500 → `0.5`.
  - `closing_spike([(49,80),(52,900),(57,120)], 50)` → `900`.
- [ ] **Step 2:** FAIL → `metrics.py` → PASS.
- [ ] **Step 3: Failing testler (`test_orchestrator.py`, sahte receiver ve gerçek QoD app'i test client'ında):**
  - `test_p3_sets_estimate_on_available`: AVAILABLE bildirimi → sahte receiver `set_gcc_estimate(2500)` aldı.
  - `test_p2_never_touches_estimate`.
  - `test_scenario_rejects_parallel_run` → ikinci `run_scenario` `ScenarioBusy` (Review Focus 5).
- [ ] **Step 4:** `orchestrator.py`'ı yaz → PASS.
- [ ] **Step 5: Doğrulama (gerçek):** Konteynerde P2 senaryosu → `runs/*-P2.json` oluşur, `t_to_target_s` > P3 koşusundakinden büyük. İki değer not edilir.
- [ ] **Step 6: Commit** `feat: orkestratör, P2/P3 ve ölçümler`

### Task 6: Panel ve tek komutla başlatma

**Files:**
- Create: `app/web.py`, `app/static/index.html`, `app/static/app.js`, `app/static/chart.umd.min.js` (Chart.js 4.4.x, dosya olarak), `run.sh`

**Interfaces:**
- Consumes: Orchestrator, Receiver.
- Produces: `GET /` panel; `GET /video.mjpg` (~15 fps MJPEG, `latest_jpeg()`); `GET /ws` (1 sn'de bir `stats`, anlık `api_log`, `qod_state`, `result` olayları); `POST /api/scenario/{P2|P3}`, `POST /api/load/{on|off}`, `POST /api/qod/{request|delete}`, `POST /api/policy/{P2|P3}`.
- Panel düzeni tasarımın Bölüm 5'indeki gibi: video + gecikme/fps, Grafik 1 (gönderilen REMB, alınan hız, kapasite 3000, profil 2500; QoD açılış/kapanış çizgisi), Grafik 2 (e2e gecikme, kayıp), QoD durumu ve kalan süre, API kaydı (JSON girintili), düğmeler, sonuç kartı (P2 | P3), Global Constraints'teki alt bilgi.
- `run.sh`: `net/setup.sh` → QoD servisini arka planda başlat → `app.web`'i başlat → `ip netns exec edge python -m media.sender` → `http://<host>:8080` adresini yazdır.

- [ ] **Step 1:** `web.py` ve statik dosyaları yaz.
- [ ] **Step 2: Doğrulama:** Mac'te `make up` → tarayıcıda `http://localhost:8080`: video oynar, grafikler akar.
- [ ] **Step 3: Doğrulama:** "Senaryo: P2" sonra "Senaryo: P3" → API kaydında `POST /sessions → 201`, `AVAILABLE`, `DURATION_EXPIRED` görünür; sonuç kartında iki sütun dolar; P3 süresi daha kısa.
- [ ] **Step 4:** Senaryo çalışırken tekrar düğmeye bas → panelde "senaryo zaten çalışıyor" uyarısı.
- [ ] **Step 5:** İnternet kapalıyken sayfayı yenile → grafikler yine çalışır (CDN yok).
- [ ] **Step 6: Commit** `feat: panel ve tek komutla başlatma`

### Task 7: Raspberry Pi'ye taşıma ve README

**Files:**
- Create: `README.md`, `scripts/pi_install.sh`

**Interfaces:**
- Produces: Pi'de `scripts/pi_install.sh` (Docker'ı resmî betikle kurar, `docker compose` ile imajı derler), README'de adım adım: Raspberry Pi OS Lite 64-bit yazma (Raspberry Pi Imager, SSH açık), demo klasörünü kopyalama, `make up`, telefondan kişisel erişim noktası veya aynı Wi-Fi ile `http://<pi>.local:8080`. Laboratuvar sapmaları ve "emülasyon" notu README'de.

- [ ] **Step 1:** README ve kurulum betiğini yaz.
- [ ] **Step 2: Doğrulama (Pi gelince):** Pi'de `scripts/pi_install.sh && make up` → dizüstünde panel açılır; P2 ve P3 senaryoları tamamlanır.
- [ ] **Step 3: Doğrulama:** `top` ile CPU ölç; %85'i geçerse `.env`'de `VIDEO_W=480 VIDEO_H=270 FPS=20` ile yeniden dene (Global Constraints çözünürlüğünden sapma README'ye not edilir).
- [ ] **Step 4: Commit** `docs: Pi kurulumu ve README`
