# AUGURY ATLAS

**Geospatial Intelligence Platform** — part of the Augury Intelligence Infrastructure family.
*See the Bigger Picture.*

Atlas coğrafi verileri, uydu görüntülerini ve konum tabanlı bilgileri analiz ederek
anlamlı analizlere ve görsel istihbarata dönüştürür.

| Yetenek / Capability | Atlas'ta karşılığı |
|---|---|
| Uydu görüntüsü entegrasyonu | Esri World Imagery + Sentinel-2 cloudless yıllık mozaikler (2016–2023), `/api/imagery` kataloğu |
| Katmanlı interaktif haritalar | MapLibre GL; altyapı, deprem, yangın, sel, risk, etki, rota katmanları |
| Şehir ve altyapı değişim takibi | İki tarihli uydu görüntüsü **swipe** karşılaştırması |
| Deprem, yangın ve sel analizi | Senaryo / gerçek olay deprem etki analizi (MMI tahmini), NASA FIRMS yangın maruziyeti, resmî taşkın alanı maruziyeti |
| Kritik altyapı envanteri | OpenStreetMap'ten otomatik keşif (havalimanı, liman, hastane, santral, baraj, rafineri, 380 kV TM, köprü) + kurum GeoJSON içe aktarma |
| Bölgesel risk haritaları | Çoklu tehlike × maruziyet risk ızgarası, ağırlıklar ayarlanabilir |
| Zamansal coğrafi karşılaştırma | Yıllık deprem aktivitesi zaman serisi + uydu görüntüsü karşılaştırması |
| Lojistik ve ulaşım analizi | En yakın tesis + OSRM yol rotası, hizmet kapsama boşluğu analizi |

Ortak Augury altyapısına bağlanan noktalar:

- **AUGURY IDENTITY** — `X-API-Key` → rol (`viewer` < `analyst` < `admin`), `atlas/identity.py`
- **AUGURY CONNECT** — USGS, NASA FIRMS, OpenStreetMap Overpass, OSRM bağlayıcıları, `atlas/connectors/`
- **AUGURY AUDIT** — her API çağrısı kim/rol/yol/sonuç/süre ile kaydedilir, `GET /api/audit`
- **AUGURY CORE** — envanter ve taşkın alanları GeoJSON ile içe aktarılır

Mimari ayrıntılar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Hızlı başlangıç

Gereksinimler: Python 3.11+, Node 20+.

```bash
make install        # backend venv + frontend npm install
make api            # http://localhost:8000  (OpenAPI: /docs)
make web            # http://localhost:5173  (/api istekleri backend'e proxy edilir)
make test           # pytest + TypeScript typecheck
```

### İlk kurulumda veri yükleme

Uygulama **demo veri içermez**; envanter boş başlar. İlk açılışta (admin):

1. **Inventory → Import from OpenStreetMap** ile Türkiye'deki gerçek tesisleri yükleyin, veya
   `curl -X POST localhost:8000/api/infrastructure/import/osm -H 'Content-Type: application/json' -d '{"categories":["airport","port","hospital","power_plant","dam","energy","substation","bridge"]}'`
2. Kurumun yetkili envanterini **Assets GeoJSON** ile yükleyin (aynı `id` güncellenir).
3. Resmî taşkın alanlarını (DSİ / AFAD) **Flood zones GeoJSON** ile yükleyin.
4. Canlı yangın verisi için ücretsiz bir `FIRMS_MAP_KEY` tanımlayın.

`ATLAS_OFFLINE=1` modunda dış servis çağrılmaz: canlı katmanlar boş döner, depremlerde yalnızca
paketlenmiş tarihî katalog kullanılır. Sahte/sentetik veri hiçbir koşulda üretilmez.
Tüm ayarlar: [`backend/.env.example`](backend/.env.example).

## API özeti

| Method | Path | Rol | Açıklama |
|---|---|---|---|
| GET | `/api/health`, `/api/me` | — | Durum, bağlayıcı modları, oturum rolü |
| GET | `/api/imagery` | viewer | Altlık ve zamansal uydu görüntüsü kataloğu |
| GET | `/api/infrastructure` | viewer | Envanter (`types`, `bbox`, `min_criticality`) |
| POST | `/api/infrastructure/import` | admin | GeoJSON FeatureCollection upsert |
| POST | `/api/infrastructure/import/osm` | admin | OpenStreetMap'ten kategori bazlı gerçek tesis keşfi |
| DELETE | `/api/infrastructure/{id}` | admin | Varlık silme |
| GET | `/api/hazards/earthquakes` | viewer | USGS (`bbox`, `start`, `end`, `min_mag`) |
| GET | `/api/hazards/earthquakes/timeline` | viewer | Ay/yıl bazlı olay sayısı ve en büyük M |
| GET | `/api/hazards/fires` | viewer | NASA FIRMS aktif yangın (`days`) |
| GET | `/api/hazards/earthquakes/historical` | viewer | Büyük tarihî depremler kataloğu |
| GET | `/api/hazards/floods` | viewer | İçe aktarılmış taşkın alanları |
| POST | `/api/hazards/floods/import` | admin | Taşkın alanı (Polygon) upsert |
| POST | `/api/analysis/earthquake` | analyst | `{lon, lat, magnitude, min_mmi}` → etkilenen varlıklar + şiddet halkaları |
| GET | `/api/analysis/wildfire` | analyst | Yangın tamponundaki varlıklar |
| GET | `/api/analysis/flood` | analyst | Taşkın alanındaki varlıklar |
| GET | `/api/analysis/risk-grid` | analyst | Bölgesel risk ızgarası (GeoJSON) |
| GET | `/api/logistics/nearest` | analyst | En yakın tesisler (+ rota) |
| GET | `/api/logistics/route` | analyst | `from=lon,lat&to=lon,lat` |
| GET | `/api/logistics/coverage` | analyst | Tesis tipine göre kapsama boşlukları |
| GET | `/api/audit` | admin | Denetim kaydı |

## Veri ve model notları

- Her katman verinin kaynağını taşır (`usgs`, `firms`, `OpenStreetMap`, `catalogue`, `unavailable`, `estimate`).
- OSM'den gelen kritiklik seviyesi etiketlerden türetilir (uluslararası havalimanı, yatak sayısı, MW, kV);
  kurum kendi değerleriyle aynı `id` üzerinden düzeltebilir.
- Paketlenmiş tek veri seti, Türkiye ve çevresindeki büyük tarihî depremlerin kataloğudur; canlı veri USGS'den gelir.
- `backend/tests/fixtures/` altındaki dosyalar yalnızca testler içindir, uygulamaya yüklenmez.
- Deprem etki analizi Atkinson & Wald (2007) şiddet denklemi + Wells & Coppersmith (1994)
  kırılma uzunluğu düzeltmesi kullanan bir **ön değerlendirme (screening)** modelidir; ShakeMap değildir.
- Risk skoru şeffaf bir önceliklendirme indeksidir: `100 × tehlike × (0.25 + 0.75 × maruziyet)`.

## Lisans

Apache-2.0 — bkz. [LICENSE](LICENSE). Harita karoları ve uydu görüntüleri kendi lisanslarına tabidir
(OpenStreetMap, CARTO, Esri, EOX Sentinel-2 cloudless — Copernicus Sentinel verisi içerir).
OpenStreetMap'ten içe aktarılan veriler © OpenStreetMap katkıcıları, ODbL lisanslıdır.
