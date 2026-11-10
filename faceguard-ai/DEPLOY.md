# FaceGuard AI — ажиллуулах ба байршуулах заавар

Аппыг гурван янзаар ажиллуулж болно:

| Арга | Юу хэрэгтэй | Хэзээ сонгох |
|---|---|---|
| **1. Нэг команд (Docker-гүй)** | Зөвхөн Python 3.11+ | Өөрийн компьютер дээр турших, хөгжүүлэх |
| **2. Интернетэд (Render / Railway)** | GitHub бүртгэл | Бусад хүнд холбоос өгч ашиглуулах |
| **3. Docker Compose (PostgreSQL + Nginx)** | Docker Desktop | Өөрийн сервер дээр бүрэн production тохиргоо ([README.md](README.md)) |

---

## 1. Нэг командаар асаах (Docker, PostgreSQL шаардлагагүй)

**Windows:** `start.bat` файлыг давхар дарна. Эсвэл PowerShell дээр:
```powershell
cd faceguard-ai
py run.py
```
**macOS / Linux:** `./start.sh` эсвэл `python3 run.py`

Анх асаахад 3–5 минут орно. Энэ үеэр `.venv` үүсгэж, backend-ийн сангуудыг суулгаж, 54 MB нүүрний landmark моделийг татаж,
SQLite өгөгдлийн сан болон нууц түлхүүр үүсгэнэ. Дараагийн удаа хэдхэн секундэд асна. Бэлэн болмогц браузер
**http://localhost:8000** хаягаар автоматаар нээгдэнэ. Анх бүртгүүлсэн хэрэглэгч **администратор** болно.

- Python байхгүй бол: <https://www.python.org/downloads/> (суулгахдаа **"Add python.exe to PATH"**-ийг чагтал).
- Node.js **хэрэггүй**: web app нь `frontend/dist` дотор бэлэн build хийгдсэн байгаа. Frontend кодоо өөрчилсөн бол
  `py run.py --build-frontend` гэж ажиллуулна (энэ үед Node.js 20+ хэрэгтэй).
- Өгөгдөл `backend/data/` хавтсанд хадгалагдана (өгөгдлийн сан болон dataset). Бүгдийг шинээр эхлүүлэх бол энэ хавтсыг устгана.
- Өөр порт ашиглах бол: `py run.py --port 9000`. Зогсоох бол: `Ctrl+C`.
- Сүлжээн дэх өөр төхөөрөмжөөс (утас гэх мэт) хандах бол `py run.py --lan` гэж асаагаад `http://<компьютерийн-IP>:8000`
  хаягаар орно. Гэхдээ браузерууд камерыг зөвхөн `localhost` эсвэл **HTTPS** дээр зөвшөөрдөг тул утаснаас камер
  ажиллуулах бол доорх 2-р аргыг ашиглана (HTTPS автоматаар ирнэ).

---

## 2. Интернетэд байршуулах

Төсөл нэг Docker контейнер болж ажиллахаар бэлтгэгдсэн (`Dockerfile` + `docker-entrypoint.sh`). Энэ контейнерт API болон web
app хамт байна. Ямар ч платформ дээр зөвхөн **`JWT_SECRET`** (32+ тэмдэгт) тохируулах шаардлагатай.

### Эхлээд: кодоо GitHub руу оруулах
```powershell
cd faceguard-ai
git init ; git add . ; git commit -m "FaceGuard AI"
# github.com дээр шинэ (private) repository үүсгээд:
git remote add origin https://github.com/<таны-нэр>/faceguard-ai.git
git push -u origin main
```

### А. Render (хамгийн хялбар, үнэгүй эхлэх боломжтой)
1. <https://render.com> дээр GitHub-аараа нэвтэрнэ.
2. **New → Blueprint** гээд repository-гоо сонгоно. `render.yaml`-ийг уншаад web app болон PostgreSQL өгөгдлийн санг үүсгэнэ.
   `JWT_SECRET` автоматаар үүснэ.
3. 5–10 минутын дараа `https://faceguard-xxxx.onrender.com` хаяг гарна. HTTPS тул камер утсан дээр ч ажиллана.

Үнэгүй багцын хязгаарлалтууд:
- 15 минут хэрэглээгүй бол сервер унтаад, дараагийн хандалтад 30–60 секунд хүлээлгэнэ.
- Үнэгүй PostgreSQL 30 хоногийн дараа устгагдана.
- Dataset файлууд redeploy хийх бүрт алга болно.

Байнга ашиглах бол `render.yaml` доторх `plan`-ийг `starter` болгож, `disk` хэсгийн комментыг арилгана.

### Б. Railway
1. <https://railway.com> → **New Project → Deploy from GitHub repo**. `railway.json`-ийн ачаар `Dockerfile`-ийг автоматаар
   олно.
2. Service → **Variables** хэсэгт `JWT_SECRET` нэмнэ. Утгыг нь PowerShell дээр
   `-join ((1..64) | % { '{0:x}' -f (Get-Random -Max 16) })` гэж үүсгэж болно.
3. Service → **Settings → Volumes** хэсэгт `/srv/data` руу volume холбоно (SQLite болон dataset-ууд үүнд хадгалагдана).
   Эсвэл **+ New → Database → PostgreSQL** нэмээд `DATABASE_URL`-ийг холбож болно.
4. **Settings → Networking → Generate Domain** дарахад HTTPS хаяг гарна.

### В. Өөрийн VPS (DigitalOcean, Hetzner гэх мэт)
```bash
docker build -t faceguard .
docker run -d --name faceguard --restart unless-stopped -p 8000:8000 \
  -e JWT_SECRET="$(openssl rand -hex 32)" -v faceguard-data:/srv/data faceguard
```
Камер ажиллахын тулд HTTPS хэрэгтэй. Үүний хамгийн хялбар арга нь урд нь Caddy тавих:
`caddy reverse-proxy --from таны-домэйн.mn --to localhost:8000`. Эсвэл README дээрх Docker Compose + TLS тохиргоог ашиглана.

### Орчны хувьсагчид (заавал биш)
| Хувьсагч | Утга |
|---|---|
| `JWT_SECRET` | **Заавал.** 32+ санамсаргүй тэмдэгт |
| `DATABASE_URL` | Хоосон бол `/srv/data` доторх SQLite ашиглана. `postgres://...` өгвөл PostgreSQL ашиглана |
| `REGISTRATION_ENABLED` | Өөрийн бүртгэлүүдээ үүсгэсний дараа `false` болговол танихгүй хүн бүртгүүлж чадахгүй |
| `APP_BASE_URL` | Нууц үг сэргээх и-мэйл дэх холбоос. Render болон Railway дээр автоматаар тохирно |
| `SMTP_*` | Нууц үг сэргээх и-мэйл илгээх ([.env.example](.env.example)) |

---

## Анхаарах зүйлс
- **Хуурамч нүүр таних AI загвар байхгүй.** Систем нүүр илрүүлж, чанарыг шалгадаг ч REAL/FAKE гэж дүгнэдэггүй. Бүх үр дүн
  `UNCERTAIN` гэж гарна ([STATUS.md](STATUS.md)).
- Интернетэд нээлттэй тавихаасаа өмнө эхний (админ) бүртгэлээ **өөрөө** үүсгэ. Эс бөгөөс хаяг таньсан хэн нэгэн түрүүлж
  бүртгүүлээд администратор болох эрсдэлтэй.
- Нүүрний зураг бол биометрийн мэдээлэл. Бусад хүмүүст ашиглуулах бол тэдний зөвшөөрлийг авч, хувийн мэдээллийн хуулийн
  шаардлагыг хангах хэрэгтэй.
- Нэг контейнерийн горимд нууц үг оролдлогын хязгаар (rate limit) санах ойд хадгалагддаг бөгөөд платформын proxy-оос ирсэн
  `X-Forwarded-For`-т итгэдэг. Олон нийтэд нээлттэй том хэмжээний ашиглалтад Docker Compose + Nginx тохиргоо илүү хамгаалалттай.
