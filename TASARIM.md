# Demo Uygulaması — Tasarım Notu

**QoD × GCC canlı demosu, Raspberry Pi 5 üzerinde**
2 Kasım 2026 · Durum: taslak, onay bekliyor

## 1. Amaç

Danışmana projemizin **nasıl çalıştığını** ve **ne fark yarattığını** canlı göstermek. Amaç konuyu öğretmek değil; hoca CAMARA ve QoD'yi biliyor. Uygulama bir edge cihazda, Raspberry Pi 5 (8 GB) üzerinde çalışır.

Demo aynı zamanda projenin ilk prototipidir. İçindeki QoD servisi ve orkestratör, dönem içindeki deneylerde aynen kullanılacak.

## 2. Gösterilecek iki şey

1. **QoD nasıl çalışıyor ve ne etki ediyor.** Ağ tıkanır, video bozulur. Uygulama CAMARA QoD API'sine oturum açma isteği atar, ağ videoya öncelik verir ve video düzelir.
2. **Projenin katkısı: P2 ile P3 farkı.**
   - **P2, gönderici habersiz:** QoD açılınca ağda videoya yer açılır, ama video uygulaması bunu bilmez. Hızını yalnızca kendi ölçümüyle, "galiba yer açıldı" diyerek yavaş yavaş artırır. Kısa bir öncelik oturumunun büyük kısmı bu sırada boşa geçer. Oturum bitince de yüksek hızda yakalanır ve gecikme sıçrar.
   - **P3, gönderici haberdar:** API'nin zaten verdiği bilgi ("öncelik açıldı, profil hızı 2,5 Mbps, bitiş 14:03:30") hız kontrolüne iletilir. Gönderici hemen profil hızına çıkar, bitişten birkaç saniye önce de kendiliğinden yavaşlar.
   - **Benzetme:** Otoyolda bir emniyet şeridi açılıyor. Habersiz sürücü şeridin açıldığını fark edene kadar şerit boş kalır. Haberdar sürücü hemen şeride girer ve şerit kapanmadan çıkar.

## 3. Hedefler, hedef olmayanlar, kaçınılacaklar

**Hedefler**
- Tek komutla başlar. Dizüstü bilgisayarın tarayıcısında tek bir sayfa açılır.
- Etki gerçektir: gerçek paketler, Linux `tc` ile gerçek darboğaz, WebRTC GCC'nin gerçek hız kontrol mantığı.
- P2 ve P3 aynı senaryoyla arka arkaya koşar; ekranda iki sonuç sayılarla karşılaştırılır.
- CAMARA API çağrıları (istek, cevap, bildirim) ekranda okunur biçimde akar.
- İnternet olmadan çalışır.

**Hedef olmayanlar (ilk sürüm)**
- Arduino, kamera (isteğe bağlı, sonra eklenebilir), gerçek operatör ağı.
- Orange/Telefónica sandbox çağrısı (sonra eklenebilir).
- SCReAM, P1 politikası, P3'ün "clamp" varyantı.
- 240 koşuluk deney ve istatistik. Demo tek tek koşu gösterir.

**Kaçınılacaklar (çalışsa bile başarısızlık sayılır)**
- Etkiyi taklit etmek; örneğin `tc` yerine videoyu bilerek bozmak.
- "Gerçek operatör ağında böyle olur" izlenimi vermek. Ekranda ağın emülasyon olduğu açıkça yazar.
- Demo sırasında terminale elle komut yazmayı gerektirmek.

## 4. Kısıtlar

- **Donanım:** Raspberry Pi 5, 8 GB, arm64. H.264 donanım kodlayıcısı yok; video yazılımla kodlanır (libx264). Çözünürlük ve kare hızı CPU bütçesine göre seçilir.
- **Pi henüz hazır değil.** Geliştirme önce Mac'te (Apple Silicon, arm64) bir Linux ortamında yapılır, sonra Pi'ye taşınır.
- **Python:** aiortc 1.15 Python 3.10 ve üstünü, `av` 14–17 sürümlerini ister. `av` 17'nin arm64 paketi abi3 ve Python 3.11+ ile çalışır. Hazır paket libx264 ve libvpx kodlayıcılarını içerir. Raspberry Pi OS Bookworm (3.11) ve Trixie (3.13) uygundur.
- Ağ namespace'leri ve `tc` için root yetkisi gerekir.
- Sınıfta internet olmayabilir: JavaScript kütüphaneleri yerelden sunulur, CDN kullanılmaz.

## 5. Ekran ve demo akışı

### Ekran (tek sayfa, Türkçe)
- **Video paneli:** Alınan video. Üstünde anlık uçtan uca gecikme (ms) ve fps.
- **Grafik 1:** Gönderilen ve alınan video bit hızı, darboğaz kapasitesi ve QoD profil hızı. QoD'nin açıldığı ve kapandığı anlar dikey çizgilerle işaretli.
- **Grafik 2:** Uçtan uca gecikme ve paket kaybı.
- **QoD durumu:** Yok / `REQUESTED` / `AVAILABLE` / `UNAVAILABLE` (nedeniyle birlikte) ve kalan süre.
- **API kaydı:** Zaman damgalı satırlar. `POST /sessions` isteği ve `201` cevabı (JSON), gelen bildirimler (CloudEvent), silme.
- **Kontroller:**
  - Otomatik: [Senaryo: P2] [Senaryo: P3]
  - Elle: [Ağı yoğunlaştır / rahatlat] [QoD iste] [Oturumu sil] ve "gönderici haberdar" anahtarı.
- **Sonuç kartı:** Her koşu için hedef hıza ulaşma süresi ve önceliğin kullanılan oranı; P2 ile P3 yan yana.
- **Alt bilgi:** "Ağ: Raspberry Pi üzerinde emüle edilmiş 3 Mbps mobil uplink (Linux tc). QoD API: CAMARA QoD 1.1.0 uyumlu yerel servis."

### Otomatik senaryo (bir koşu ~65 sn; süreler ayarlanabilir)

| Zaman | Olay |
|---|---|
| 0 sn | Video akıyor, ağ boş. |
| 10 sn | "Diğer kullanıcıların" trafiği başlar. Video bit hızı düşer, gecikme artar. |
| 20 sn | Uygulama `POST /sessions` ile 30 sn'lik bir QoD oturumu ister. |
| ~21 sn | Oturum `AVAILABLE` olur ve bildirim gelir. Ağ videoya ayrılmış kapasite verir. P2'de GCC yavaş tırmanır; P3'te uygulama tahmini profil hızına çeker. |
| ~47 sn | P3: Bitişe ~4 sn kala hız önceden düşürülür. |
| ~51 sn | Oturum biter (`DURATION_EXPIRED`). P2'de gönderici yüksek hızda yakalanır ve gecikme sıçrar. |
| 65 sn | Yük durur, koşu biter, ölçümler sonuç kartına yazılır. |

## 6. Mimari

```
 Raspberry Pi 5 (her şey bu cihazda)
 ┌──────────────────────────────────────────────────────────────────────┐
 │  [ns: edge]               [ns: net]                [kök ns: sunucu]  │
 │  Video gönderici ──────►  Yönlendirici ─────────►  Video alıcı       │
 │  (aiortc, H.264)          tc HTB darboğaz          (GCC alıcı tarafı)│
 │                           3 Mbps, RTT ~50 ms        Orkestratör      │
 │  [ns: others]                   ▲                   Panel (web)      │
 │  TCP yükleme (iperf3) ────────► │                      │             │
 │                                 │ tc komutları         │ CAMARA QoD  │
 │                           QoD servisi ◄────────────────┘ HTTP API    │
 │                           (kök ns, ayrı süreç) ──► bildirim (sink)   │
 └──────────────────────────────────────────────────────────────────────┘
                 ▲ Ethernet ya da Wi-Fi (yalnızca panel trafiği)
            Dizüstü bilgisayar: tarayıcı
```

| Bileşen | Nerede | Görevi |
|---|---|---|
| Video göndericisi | ns `edge` | aiortc. Hareketli sentetik test görüntüsünü H.264 ile gönderir; kodlayıcı hızını GCC geri bildirimine (REMB) göre ayarlar. |
| Diğer kullanıcılar | ns `others` | TCP toplu yükleme (iperf3) ile ağı yoğunlaştırır. |
| Operatör ağı (emüle) | ns `net` | Yönlendirici. Sunucuya giden çıkışında `tc` HTB darboğazı (toplam 3 Mbps) ve `netem` gecikmesi (RTT ~50 ms). |
| QoD servisi | kök ns, ayrı süreç | CAMARA QoD 1.1.0 ve QoS Profiles uç noktaları. Oturum açılınca HTB'ye öncelikli sınıf ekler, bitince kaldırır, bildirim gönderir. |
| Uygulama sunucusu | kök ns | aiortc alıcısı (GCC'nin gecikme tabanlı tahmincisi, REMB üretir), orkestratör (QoD istemcisi ve P3 mantığı) ve panel web sunucusu. |
| Panel | Dizüstü bilgisayarın tarayıcısı | Pi'nin sunduğu sayfa; canlı veri WebSocket ile gelir. |

Arka plan trafiği ayrı bir namespace'ten ve video sunucusundan farklı bir hedef IP'ye gider. Böylece CAMARA oturumundaki "cihaz + uygulama sunucusu" eşleşmesi yalnızca videoyu kapsar ve port belirtmek gerekmez.

## 7. Bileşen ayrıntıları

### 7.1 QoD servisi (projenin ana parçası)
- **Uç noktalar:**
  - `POST /sessions`, `GET /sessions/{id}`, `DELETE /sessions/{id}`, `POST /sessions/{id}/extend`, `POST /retrieve-sessions` (yol öneki `/quality-on-demand/v1`).
  - `POST /retrieve-qos-profiles`, `GET /qos-profiles/{name}` (yol öneki `/qos-profiles/v1`).
- **Durumlar:** `REQUESTED` → ayarlanabilir etkinleşme gecikmesi (varsayılan 1 sn) → `AVAILABLE` → `UNAVAILABLE`. Nedenler: `DURATION_EXPIRED`, `DELETE_REQUESTED`. Cevaplarda `startedAt` ve `expiresAt` bulunur.
- **Kurallar:** Aynı cihaz için ikinci oturum `409` döner. `duration` profilin alt ve üst sınırı içinde olmalı. Hatalı isteklere spesifikasyondaki `400`/`404`/`422` kodları döner.
- **Önceliği uygulama:** Oturum `AVAILABLE` olunca `net` namespace'indeki HTB'ye öncelikli bir sınıf (hız = profilin hedef hızı, tavan = toplam kapasite) ve cihaz IP → sunucu IP filtresi eklenir. Oturum bitince kaldırılır.
- **Bildirim:** `sink` adresine CloudEvent gönderilir; tür `org.camaraproject.quality-on-demand.v1.qos-status-changed`.
- **Profiller:** En az iki video profili; örneğin `QOS_VIDEO_M` 1,5 Mbps ve `QOS_VIDEO_L` 2,5 Mbps. Kesin değerleri builder belirler.
- **Laboratuvar sapmaları (belgelenecek):** Yetkilendirme sabit bir token ile yapılır (OIDC yok). `sink` için `http` kabul edilir; spesifikasyon `https` istiyor.

### 7.2 Orkestratör
- **Tetikleme:** Senaryoda zamanlı, elle düğmeyle, ya da basit bir eşikle (gecikme belirli bir süre boyunca X ms'nin üstünde).
- QoD isteklerini gerçek HTTP ile yapar; her istek ve cevap API kaydına düşer.
- **P2:** Hiçbir şey yapmaz; GCC kendi başına tepki verir.
- **P3:**
  - `AVAILABLE` bildirimi gelince alıcıdaki GCC tahminini profil hızına ayarlar (aiortc `AimdRateControl.set_estimate`). Gönderici bir sonraki REMB'de hızlanır.
  - `expiresAt` − Δ anında (varsayılan Δ = 4 sn) tahmini QoD öncesi hıza indirir.
  - Kaynak kodda doğrulandı: `_clamp_bitrate` üst sınırı `max(1.5 × throughput, current_bitrate)` olduğu için ayarlanan tahmin geri çekilmez.

### 7.3 Gönderici ve alıcı
- **Kütüphane ve kodlayıcı:** aiortc ile H.264. aiortc'nin H.264 için varsayılan üst sınırı 3 Mbps; profil hızını kapsayacak şekilde ayarlanır.
- **Sinyalleşme:** Alıcının HTTP uç noktasına offer/answer gönderilir (aiortc örneklerindeki gibi). ICE yalnızca yerel adresleri kullanır.
- **Uçtan uca gecikme:** Gönderici ve alıcı aynı Pi saatini kullandığı için, kareye eklenen gönderim zamanından doğrudan ölçülür.

### 7.4 Panel
- Alıcının çözdüğü kareler tarayıcıya aktarılır (MJPEG ya da benzeri; yöntemi builder seçer).
- Grafik kütüphanesi yerelden sunulur.

## 8. Ekranda gösterilen ölçümler

- **Hedef hıza ulaşma süresi:** `AVAILABLE` sonrasında alınan bit hızının profil hızının %90'ına ulaştığı ana kadar geçen süre (sn). Hiç ulaşamazsa "ulaşamadı" yazar ve ulaşılan en yüksek hız gösterilir.
- **Önceliğin kullanılan oranı:** Oturum boyunca alınan video bitleri / (profil hızı × oturum süresi).
- **Kapanış sıçraması:** Oturum bittikten sonraki 5 sn içindeki en yüksek uçtan uca gecikme.
- **Sürekli:** bit hızı, gecikme, kayıp, fps.

## 9. Geliştirme ve Pi'ye taşıma

- **Aşama A (Pi yokken):** Mac'te arm64 Linux. Önce Docker Desktop'ta ayrıcalıklı bir konteyner denenir: netns ve `tc` HTB çalışıyor mu? Çalışmazsa UTM'de Debian 13 arm64 sanal makine kullanılır; Raspberry Pi OS Trixie'ye en yakın ortam budur.
- **Aşama B (Pi hazır olunca):**
  - Raspberry Pi OS Lite 64-bit üzerine tek bir kurulum betiği.
  - Bağlantı: En kolay yol olarak Pi ve dizüstü bilgisayar aynı telefonun kişisel erişim noktasına bağlanır; ek ayar gerekmez. Okul ağları cihazları birbirinden yalıtabildiği için okul Wi-Fi'ına güvenilmez. Pi'nin kendi erişim noktasını açması ilk sürümde yok.
  - İsteğe bağlı: Pi açılınca demo kendiliğinden başlar (systemd).
- **Yedek:** Pi'de sorun çıkarsa aynı demo Mac'teki Linux ortamında çalıştırılabilir.
- **Kod yeri:** `~/Downloads/bitirme/demo/`; ileride ortak GitHub deposuna taşınır.

## 10. Kararlar

**Ekibin verdiği kararlar**
- Demo, projenin çalışma şeklini ve etkisini gösterecek; hoca konuyu biliyor.
- Yalnızca Raspberry Pi 5 kullanılacak; Arduino yok; sade tutulacak.
- Pi şu an hazır değil; plan buna göre yapılacak.

**Teknik kararlar (değiştirilebilir)**
- **WebRTC kütüphanesi: aiortc (Python).** GCC'nin alıcı tarafı tahmincisi Python'da ve erişilebilir olduğu için P3 birkaç satırla uygulanır; derleme gerektirmez. Bedeli: tarayıcılardaki en güncel GCC değil, libwebrtc'nin REMB tabanlı eski GCC'si. Bu, Carlucci ve ark. (2016) çalışmasında incelenen sürüm; hız artışı %8/sn, düşüşü 0,85 katsayısıyla.
- Kamera yerine hareketli sentetik test görüntüsü.
- Darboğaz 3 Mbps, RTT ~50 ms, QoD oturumu 30 sn, etkinleşme gecikmesi 1 sn. Hepsi ayarlanabilir.
- Arka plan yükü ayrı bir "diğer kullanıcılar" namespace'inden gelen TCP trafiği.
- P3'ün tek varyantı ("hedef"); "clamp" varyantı ilk sürümde yok.
- Pi ekransız çalışır; arayüz Türkçe.
- Her koşunun ölçümleri ve API kaydı `runs/` klasörüne dosya olarak kaydedilir; tezde ve sunumda kullanılabilir.
- Plan, her adımın sonunda gösterilebilir bir sürüm bırakacak şekilde sıralanır. Önce "QoD ağı rahatlatıyor" etkisi çalışır, sonra P2/P3 karşılaştırması eklenir. Demo tarihi ne olursa olsun elde çalışan bir sürüm olur.

## 11. Builder'a bırakılanlar

Web çatısı, grafik kütüphanesi, görüntü aktarım yöntemi, eşik ve profil değerleri, namespace kurulum betiğinin ayrıntıları, dosya düzeni ve test yaklaşımı.

## 12. Riskler ve yedekler

| Risk | Yedek |
|---|---|
| Pi 5'in CPU'su kodlama, çözme ve panele birlikte yetmez | Çözünürlüğü ve fps'i düşürmek (640×360, 15–20 fps) |
| Docker'da netns veya `tc` çalışmaz | UTM'de Debian sanal makine |
| aiortc'nin H.264'ü sorun çıkarır | VP8. Üst sınırı 1,5 Mbps olduğu için darboğaz ölçeği küçültülür. |
| P2 ile P3 arasındaki fark beklenenden küçük çıkar | Süre, kapasite ve yük ayarlanır; sonuç olduğu gibi gösterilir, saklanmaz |
| Demo yerinde ağ yok ya da cihazlar yalıtılmış | Ethernet kablosu veya Pi'nin kendi Wi-Fi erişim noktası; her şey yerelde |

## 13. Açık soru

Yok. Demo tarihi belli değil; bu nedenle plan, her adımda çalışan bir sürüm bırakacak şekilde sıralanır (bkz. Bölüm 10).
