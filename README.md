# QoD × GCC canlı demo

CAMARA Quality on Demand (QoD) API'siyle verilen geçici ağ önceliğinin, gerçek zamanlı video göndericisine etkisini canlı gösteren demo. Raspberry Pi 5 üzerinde (edge cihaz) çalışır; panel dizüstü bilgisayarın tarayıcısında açılır.

Gösterdiği iki şey:
1. **QoD'nin etkisi:** Ağ yoğunlaşınca video bozulur. Uygulama CAMARA QoD API'sinden oturum ister, ağ videoya öncelik verir ve video düzelir.
2. **Projenin katkısı (P2 ile P3):** Gönderici QoD'den habersizken (P2) önceliğin büyük kısmı boşa gider ve oturum bitince gecikme sıçrar. Haberdarken (P3) gönderici hemen hızlanır, bitişten önce kendiliğinden yavaşlar.

Tasarım: `TASARIM.md` · Uygulama planı: `PLAN.md`

## Mac'te çalıştırma

Gerekli: Docker Desktop (açık olmalı).

```bash
cd ~/Downloads/bitirme/demo
docker compose up -d --build     # ilk seferde imaj derlenir
open http://localhost:8080
```

Durdurmak için: `docker compose down`

## Raspberry Pi 5'te çalıştırma

1. **İşletim sistemi:** Raspberry Pi Imager ile microSD karta **Raspberry Pi OS Lite (64-bit)** yazın. Imager'ın ayarlarında:
   - Ana bilgisayar adı: `qoddemo`
   - Kullanıcı adı ve şifre belirleyin
   - SSH'yi açın
   - Wi-Fi olarak **telefonunuzun kişisel erişim noktasını** girin
2. **Bağlantı:** Pi'yi açın. Dizüstü bilgisayarı da aynı telefon erişim noktasına bağlayın.
3. **Demoyu kopyalayın:** Mac'te çalıştırın:
   ```bash
   scp -r ~/Downloads/bitirme/demo <kullanıcı>@qoddemo.local:~/demo
   ```
4. **Kurulum (bir kez):**
   ```bash
   ssh <kullanıcı>@qoddemo.local
   cd ~/demo && ./scripts/pi_install.sh
   ```
5. **Başlatma:** `sudo docker compose up -d`. Panel: **http://qoddemo.local:8080**

Demo, Pi her açıldığında kendiliğinden başlar (`restart: unless-stopped`).

**CPU yetmezse** (video takılıyorsa ya da `top` %85'in üstündeyse) daha küçük çözünürlükle başlatın:
```bash
sudo VIDEO_W=480 VIDEO_H=270 FPS=20 docker compose up -d
```

## Demo nasıl yapılır (~3 dakika)

1. Paneli açın. Video akıyor, gecikme ~50 ms.
2. **"Senaryo: P2"** düğmesine basın. Sırasıyla şunlar olur:
   - 10. sn: Ağ yoğunlaşır; video hızı düşer, gecikme saniyelere çıkar.
   - 20. sn: Uygulama QoD ister. **CAMARA API kaydında** profil sorgusu, `POST /sessions → 201` ve bildirimler görünür.
   - Oturum açılınca gecikme hemen düşer, ama gönderici habersiz olduğu için hızı çok yavaş artar.
   - 30 sn sonra oturum biter ve gecikme sıçrar.
3. Bitince **"Senaryo: P3"** düğmesine basın. Aynı akışta gönderici hemen profil hızına çıkar ve bitişten önce yavaşlar.
4. **Sonuç tablosu** iki politikayı sayılarla karşılaştırır.

Elle kontrol düğmeleriyle ağı yoğunlaştırabilir, QoD isteyebilir, oturumu silebilir ve göndericiyi P2/P3 arasında değiştirebilirsiniz.

Docker konteynerinde (Mac) yapılan örnek koşu:

| | P2 habersiz | P3 haberdar |
|---|---|---|
| Hedef hıza ulaşma süresi | ulaşamadı (en yüksek 1868 kbps) | 1,8 sn |
| Önceliğin kullanılan oranı | %38 | %89 |
| Kapanış sıçraması | 4365 ms | 508 ms |

Her koşunun tüm ölçümleri ve API kaydı `runs/` klasörüne JSON olarak kaydedilir.

## Mimari

Her şey tek bir konteynerde, üç ağ namespace'iyle çalışır:

| Parça | Yer | Görevi |
|---|---|---|
| Edge video göndericisi | `edge` (10.10.1.2) | aiortc ile sentetik test görüntüsünü H.264 olarak gönderir |
| Diğer kullanıcılar | `others` (10.10.3.2) | 4 paralel TCP yükleme (iperf3) |
| Operatör ağı (emüle) | `net` | 3 Mbps uplink darboğazı (`tc` HTB), RTT 50 ms |
| QoD servisi | kök, port 9091 | CAMARA QoD 1.1.0 + QoS Profiles; oturum açılınca `tc` ile öncelik sınıfı ekler |
| Uygulama sunucusu | kök, 10.10.2.2:8080 | Video alıcısı (GCC), orkestratör (QoD istemcisi, P2/P3), panel |

## Sınırlılıklar ve laboratuvar sapmaları

- **Ağ emülasyondur.** Gerçek operatör ağı veya radyo yoktur; sonuçlar "mekanizmalar aynı koşullarda böyle davranır" der, "operatör ağında şu kadar kazanç olur" demez.
- **Kullanıcı başına kuyruk:** Öncelik dışı trafik, akış başına adil kuyrukta (`sfq`) bekler. Bu, bir mobil hücrede her kullanıcının kendi kuyruğunun olmasını taklit eder.
- **GCC'nin yarısı:** aiortc, GCC'nin alıcı tarafındaki gecikme tabanlı kısmını (REMB) uygular. libwebrtc'deki gönderici tarafı kayıp tabanlı kural yoktur.
- **P3 hedefi profil hızının %90'ıdır.** Profil hızı ağ katmanı hızıdır; kalan %10 paket başlıkları ve yeniden gönderimler içindir.
- **P3 kancası:** aiortc'nin özel alanına erişir; bu yüzden aiortc sürümü `1.15.0`'a sabitlenmiştir.
- **CAMARA'dan sapmalar:** Yetkilendirme sabit bir token ile yapılır (`Bearer demo-token`, OIDC yok). Bildirim adresi (`sink`) için `http` kabul edilir; spesifikasyon `https` ister.
- Videonun alt bandındaki karıncalı doku bilerek konmuştur: kodlayıcının profil hızını doldurabilmesi için gerçek kameradaki ayrıntıyı temsil eder. Sol üstteki siyah-beyaz bloklar, gecikmeyi ölçmek için kareye gömülen zaman damgasıdır.

## Testler

```bash
docker compose run --rm --no-deps demo python -m pytest -q
# gerçek tc testi dahil:
docker compose run --rm --no-deps demo bash -c './net/setup.sh >/dev/null && python -m pytest -q'
```
