import hashlib
from datetime import datetime, time, timedelta

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db, init_db

app = FastAPI(title="IoT Attendance API", version="1.0.0")
security = HTTPBearer()
app.mount("/static", StaticFiles(directory="frontend"), name="static")

SECRET_KEY = "change-this-secret-key-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_default_config()
    seed_default_admin()


def seed_default_config() -> None:
    db = next(get_db())
    try:
        defaults = {
            "hadir_batas": "07:00:00",
            "terlambat_batas": "07:15:00",
        }
        for key, value in defaults.items():
            existing = db.query(models.AppConfig).filter(models.AppConfig.key == key).first()
            if not existing:
                db.add(models.AppConfig(key=key, value=value))
        db.commit()
    finally:
        db.close()


def hash_password(password: str) -> str:
    # Placeholder hashing sederhana. Pada produksi gunakan passlib/bcrypt.
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def seed_default_admin() -> None:
    db = next(get_db())
    try:
        existing_admin = db.query(models.User).filter(models.User.username == "admin").first()
        if not existing_admin:
            db.add(
                models.User(
                    username="admin",
                    password=hash_password("kelompokiot"),
                    role=models.UserRole.ADMIN,
                )
            )
            db.commit()
    finally:
        db.close()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def authenticate_user(db: Session, username: str, password: str):
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if user.password != hash_password(password):
        return None
    return user


def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Token tidak valid atau sudah kedaluwarsa",
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user


def get_current_siswa_jwt(
    current_user: models.User = Depends(get_current_user_jwt),
    db: Session = Depends(get_db),
):
    if current_user.role != models.UserRole.SISWA:
        raise HTTPException(status_code=403, detail="Akses ditolak. Role Siswa diperlukan")

    siswa = db.query(models.Siswa).filter(models.Siswa.user_id == current_user.id).first()
    if not siswa:
        raise HTTPException(status_code=404, detail="Profil siswa tidak ditemukan")
    return siswa


def parse_hms(value: str) -> time:
    return datetime.strptime(value, "%H:%M:%S").time()


def get_config_time(db: Session, key: str, fallback: str) -> time:
    cfg = db.query(models.AppConfig).filter(models.AppConfig.key == key).first()
    if not cfg:
        return parse_hms(fallback)
    return parse_hms(cfg.value)


def get_current_admin(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None),
):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Header x-user-id wajib diisi")

    user = db.query(models.User).filter(models.User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User tidak ditemukan")

    if user.role != models.UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Akses ditolak. Role Admin diperlukan")

    return user


def get_current_guru(
    db: Session = Depends(get_db),
    x_user_id: int | None = Header(default=None),
):
    if x_user_id is None:
        raise HTTPException(status_code=401, detail="Header x-user-id wajib diisi")

    user = db.query(models.User).filter(models.User.id == x_user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User tidak ditemukan")

    if user.role != models.UserRole.GURU:
        raise HTTPException(status_code=403, detail="Akses ditolak. Role Guru diperlukan")

    return user


def determine_attendance_status(db: Session, scan_time: datetime) -> models.StatusPresensi:
    """
    Menentukan status otomatis berdasarkan waktu scan:
    - <= 07:00:00   : Hadir
    - 07:00:01-07:15:00 : Terlambat
    - > 07:15:00    : Terlambat

    Catatan:
    Penetapan "Alpa" idealnya dijalankan oleh job terjadwal untuk siswa
    yang tidak melakukan scan sama sekali sampai batas waktu tertentu.
    """
    current_time = scan_time.time()
    hadir_batas = get_config_time(db, "hadir_batas", "07:00:00")
    terlambat_batas = get_config_time(db, "terlambat_batas", "07:15:00")

    if current_time <= hadir_batas:
        return models.StatusPresensi.HADIR

    if current_time > hadir_batas and current_time <= terlambat_batas:
        return models.StatusPresensi.TERLAMBAT

    return models.StatusPresensi.TERLAMBAT


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Username atau password salah")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value},
        expires_delta=access_token_expires,
    )
    return schemas.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
    )


@app.post("/api/rfid/scan", response_model=schemas.RFIDScanResponse)
def scan_rfid(payload: schemas.RFIDScanRequest, db: Session = Depends(get_db)):
    # 1) Cek UID RFID pada tabel siswa.
    siswa = db.query(models.Siswa).filter(models.Siswa.uid_rfid == payload.uid_rfid).first()
    if not siswa:
        raise HTTPException(status_code=404, detail="UID RFID tidak terdaftar")

    # 2) Tentukan status berdasarkan waktu scan saat ini.
    scan_time = datetime.now()
    status = determine_attendance_status(db, scan_time)

    # 3) Simpan hasil scan ke tabel presensi.
    data_presensi = models.Presensi(
        siswa_id=siswa.id,
        waktu_scan=scan_time,
        status=status,
        keterangan="Scan RFID via ESP32",
    )
    db.add(data_presensi)
    db.commit()

    # 4) Kembalikan data ringkas untuk tampilan LCD alat.
    return schemas.RFIDScanResponse(
        nama_siswa=siswa.nama,
        jam_scan=scan_time,
        status=status.value,
    )


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


@app.post("/admin/siswa", response_model=schemas.AdminSiswaOut)
def admin_create_siswa(
    payload: schemas.AdminSiswaCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    existing_user = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username sudah digunakan")

    existing_uid = db.query(models.Siswa).filter(models.Siswa.uid_rfid == payload.uid_rfid).first()
    if existing_uid:
        raise HTTPException(status_code=400, detail="UID RFID sudah terdaftar")

    user = models.User(
        username=payload.username,
        password=hash_password(payload.password),
        role=models.UserRole.SISWA,
    )
    db.add(user)
    db.flush()

    siswa = models.Siswa(
        user_id=user.id,
        uid_rfid=payload.uid_rfid,
        nama=payload.nama,
        kelas=payload.kelas,
        no_ortu=payload.no_ortu,
    )
    db.add(siswa)
    db.commit()
    db.refresh(siswa)

    return schemas.AdminSiswaOut(
        id=siswa.id,
        user_id=user.id,
        username=user.username,
        uid_rfid=siswa.uid_rfid,
        nama=siswa.nama,
        kelas=siswa.kelas,
        no_ortu=siswa.no_ortu,
    )


@app.get("/admin/siswa", response_model=list[schemas.AdminSiswaOut])
def admin_list_siswa(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    rows = (
        db.query(models.Siswa, models.User)
        .join(models.User, models.Siswa.user_id == models.User.id)
        .order_by(models.Siswa.nama.asc())
        .all()
    )
    return [
        schemas.AdminSiswaOut(
            id=siswa.id,
            user_id=user.id,
            username=user.username,
            uid_rfid=siswa.uid_rfid,
            nama=siswa.nama,
            kelas=siswa.kelas,
            no_ortu=siswa.no_ortu,
        )
        for siswa, user in rows
    ]


@app.put("/admin/siswa/{siswa_id}", response_model=schemas.AdminSiswaOut)
def admin_update_siswa(
    siswa_id: int,
    payload: schemas.AdminSiswaUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    siswa = db.query(models.Siswa).filter(models.Siswa.id == siswa_id).first()
    if not siswa:
        raise HTTPException(status_code=404, detail="Data siswa tidak ditemukan")

    user = db.query(models.User).filter(models.User.id == siswa.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User siswa tidak ditemukan")

    if payload.username and payload.username != user.username:
        user_exists = db.query(models.User).filter(models.User.username == payload.username).first()
        if user_exists:
            raise HTTPException(status_code=400, detail="Username sudah digunakan")
        user.username = payload.username

    if payload.password:
        user.password = hash_password(payload.password)

    if payload.uid_rfid and payload.uid_rfid != siswa.uid_rfid:
        uid_exists = db.query(models.Siswa).filter(models.Siswa.uid_rfid == payload.uid_rfid).first()
        if uid_exists:
            raise HTTPException(status_code=400, detail="UID RFID sudah terdaftar")
        siswa.uid_rfid = payload.uid_rfid

    if payload.nama is not None:
        siswa.nama = payload.nama
    if payload.kelas is not None:
        siswa.kelas = payload.kelas
    if payload.no_ortu is not None:
        siswa.no_ortu = payload.no_ortu

    db.commit()
    db.refresh(siswa)

    return schemas.AdminSiswaOut(
        id=siswa.id,
        user_id=user.id,
        username=user.username,
        uid_rfid=siswa.uid_rfid,
        nama=siswa.nama,
        kelas=siswa.kelas,
        no_ortu=siswa.no_ortu,
    )


@app.delete("/admin/siswa/{siswa_id}")
def admin_delete_siswa(
    siswa_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    siswa = db.query(models.Siswa).filter(models.Siswa.id == siswa_id).first()
    if not siswa:
        raise HTTPException(status_code=404, detail="Data siswa tidak ditemukan")

    user = db.query(models.User).filter(models.User.id == siswa.user_id).first()

    db.query(models.Presensi).filter(models.Presensi.siswa_id == siswa.id).delete()
    db.delete(siswa)
    if user:
        db.delete(user)
    db.commit()

    return {"message": "Data siswa berhasil dihapus"}


@app.post("/admin/guru", response_model=schemas.AdminGuruOut)
def admin_create_guru(
    payload: schemas.AdminGuruCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    existing_user = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username sudah digunakan")

    existing_nip = db.query(models.Guru).filter(models.Guru.nip == payload.nip).first()
    if existing_nip:
        raise HTTPException(status_code=400, detail="NIP sudah terdaftar")

    user = models.User(
        username=payload.username,
        password=hash_password(payload.password),
        role=models.UserRole.GURU,
    )
    db.add(user)
    db.flush()

    guru = models.Guru(
        user_id=user.id,
        nama=payload.nama,
        nip=payload.nip,
        mata_pelajaran=payload.mata_pelajaran,
    )
    db.add(guru)
    db.commit()
    db.refresh(guru)

    return schemas.AdminGuruOut(
        id=guru.id,
        user_id=user.id,
        username=user.username,
        nama=guru.nama,
        nip=guru.nip,
        mata_pelajaran=guru.mata_pelajaran,
    )


@app.get("/admin/guru", response_model=list[schemas.AdminGuruOut])
def admin_list_guru(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    rows = (
        db.query(models.Guru, models.User)
        .join(models.User, models.Guru.user_id == models.User.id)
        .order_by(models.Guru.nama.asc())
        .all()
    )
    return [
        schemas.AdminGuruOut(
            id=guru.id,
            user_id=user.id,
            username=user.username,
            nama=guru.nama,
            nip=guru.nip,
            mata_pelajaran=guru.mata_pelajaran,
        )
        for guru, user in rows
    ]


@app.put("/admin/guru/{guru_id}", response_model=schemas.AdminGuruOut)
def admin_update_guru(
    guru_id: int,
    payload: schemas.AdminGuruUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    guru = db.query(models.Guru).filter(models.Guru.id == guru_id).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Data guru tidak ditemukan")

    user = db.query(models.User).filter(models.User.id == guru.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User guru tidak ditemukan")

    if payload.username and payload.username != user.username:
        user_exists = db.query(models.User).filter(models.User.username == payload.username).first()
        if user_exists:
            raise HTTPException(status_code=400, detail="Username sudah digunakan")
        user.username = payload.username

    if payload.password:
        user.password = hash_password(payload.password)

    if payload.nip and payload.nip != guru.nip:
        nip_exists = db.query(models.Guru).filter(models.Guru.nip == payload.nip).first()
        if nip_exists:
            raise HTTPException(status_code=400, detail="NIP sudah terdaftar")
        guru.nip = payload.nip

    if payload.nama is not None:
        guru.nama = payload.nama
    if payload.mata_pelajaran is not None:
        guru.mata_pelajaran = payload.mata_pelajaran

    db.commit()
    db.refresh(guru)

    return schemas.AdminGuruOut(
        id=guru.id,
        user_id=user.id,
        username=user.username,
        nama=guru.nama,
        nip=guru.nip,
        mata_pelajaran=guru.mata_pelajaran,
    )


@app.delete("/admin/guru/{guru_id}")
def admin_delete_guru(
    guru_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    guru = db.query(models.Guru).filter(models.Guru.id == guru_id).first()
    if not guru:
        raise HTTPException(status_code=404, detail="Data guru tidak ditemukan")

    user = db.query(models.User).filter(models.User.id == guru.user_id).first()

    db.delete(guru)
    if user:
        db.delete(user)
    db.commit()

    return {"message": "Data guru berhasil dihapus"}


@app.get("/admin/stats", response_model=schemas.AdminStatsOut)
def admin_stats_today(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    today = datetime.now().date()

    hadir_count = (
        db.query(func.count(func.distinct(models.Presensi.siswa_id)))
        .filter(
            and_(
                func.date(models.Presensi.waktu_scan) == today,
                models.Presensi.status == models.StatusPresensi.HADIR,
            )
        )
        .scalar()
        or 0
    )

    terlambat_count = (
        db.query(func.count(func.distinct(models.Presensi.siswa_id)))
        .filter(
            and_(
                func.date(models.Presensi.waktu_scan) == today,
                models.Presensi.status == models.StatusPresensi.TERLAMBAT,
            )
        )
        .scalar()
        or 0
    )

    scanned_today_count = (
        db.query(func.count(func.distinct(models.Presensi.siswa_id)))
        .filter(func.date(models.Presensi.waktu_scan) == today)
        .scalar()
        or 0
    )
    total_siswa = db.query(func.count(models.Siswa.id)).scalar() or 0
    alpa_count = max(total_siswa - scanned_today_count, 0)

    return schemas.AdminStatsOut(
        hadir=hadir_count,
        terlambat=terlambat_count,
        alpa=alpa_count,
    )


@app.put("/admin/config/attendance-time", response_model=schemas.AttendanceConfigOut)
def admin_update_attendance_config(
    payload: schemas.AttendanceConfigUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    hadir_time = parse_hms(payload.hadir_batas)
    terlambat_time = parse_hms(payload.terlambat_batas)
    if terlambat_time <= hadir_time:
        raise HTTPException(
            status_code=400,
            detail="terlambat_batas harus lebih besar dari hadir_batas",
        )

    for key, value in {
        "hadir_batas": payload.hadir_batas,
        "terlambat_batas": payload.terlambat_batas,
    }.items():
        cfg = db.query(models.AppConfig).filter(models.AppConfig.key == key).first()
        if cfg:
            cfg.value = value
        else:
            db.add(models.AppConfig(key=key, value=value))

    db.commit()
    return schemas.AttendanceConfigOut(
        hadir_batas=payload.hadir_batas,
        terlambat_batas=payload.terlambat_batas,
    )


@app.get("/admin/config/attendance-time", response_model=schemas.AttendanceConfigOut)
def admin_get_attendance_config(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    hadir_batas = get_config_time(db, "hadir_batas", "07:00:00").strftime("%H:%M:%S")
    terlambat_batas = get_config_time(db, "terlambat_batas", "07:15:00").strftime("%H:%M:%S")
    return schemas.AttendanceConfigOut(
        hadir_batas=hadir_batas,
        terlambat_batas=terlambat_batas,
    )


@app.get("/guru/presensi-kelas/{kelas}", response_model=list[schemas.GuruKelasPresensiItem])
def guru_presensi_kelas_hari_ini(
    kelas: str,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_guru),
):
    today = datetime.now().date()
    siswa_list = (
        db.query(models.Siswa)
        .filter(models.Siswa.kelas == kelas)
        .order_by(models.Siswa.nama.asc())
        .all()
    )

    result: list[schemas.GuruKelasPresensiItem] = []
    for siswa in siswa_list:
        latest_today = (
            db.query(models.Presensi)
            .filter(
                and_(
                    models.Presensi.siswa_id == siswa.id,
                    func.date(models.Presensi.waktu_scan) == today,
                )
            )
            .order_by(models.Presensi.waktu_scan.desc())
            .first()
        )

        if latest_today:
            result.append(
                schemas.GuruKelasPresensiItem(
                    siswa_id=siswa.id,
                    nama=siswa.nama,
                    kelas=siswa.kelas,
                    jam_scan=latest_today.waktu_scan,
                    status=latest_today.status.value,
                    keterangan=latest_today.keterangan,
                )
            )
        else:
            result.append(
                schemas.GuruKelasPresensiItem(
                    siswa_id=siswa.id,
                    nama=siswa.nama,
                    kelas=siswa.kelas,
                    jam_scan=None,
                    status=models.StatusPresensi.ALPA.value,
                    keterangan="Belum ada scan hari ini",
                )
            )

    return result


@app.put("/guru/presensi/override", response_model=schemas.GuruManualOverrideResponse)
def guru_manual_override_presensi(
    payload: schemas.GuruManualOverrideRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_guru),
):
    siswa = db.query(models.Siswa).filter(models.Siswa.id == payload.siswa_id).first()
    if not siswa:
        raise HTTPException(status_code=404, detail="Siswa tidak ditemukan")

    today = datetime.now().date()
    latest_today = (
        db.query(models.Presensi)
        .filter(
            and_(
                models.Presensi.siswa_id == siswa.id,
                func.date(models.Presensi.waktu_scan) == today,
            )
        )
        .order_by(models.Presensi.waktu_scan.desc())
        .first()
    )

    status_enum = models.StatusPresensi(payload.status)
    if latest_today:
        latest_today.status = status_enum
        latest_today.keterangan = payload.keterangan
        record = latest_today
    else:
        record = models.Presensi(
            siswa_id=siswa.id,
            waktu_scan=datetime.now(),
            status=status_enum,
            keterangan=payload.keterangan,
        )
        db.add(record)

    db.commit()
    db.refresh(record)

    return schemas.GuruManualOverrideResponse(
        siswa_id=siswa.id,
        nama=siswa.nama,
        kelas=siswa.kelas,
        jam_scan=record.waktu_scan,
        status=record.status.value,
        keterangan=record.keterangan,
    )


@app.get(
    "/guru/export/presensi-bulanan",
    response_model=schemas.GuruExportPresensiBulananResponse,
)
def guru_export_presensi_bulanan(
    kelas: str,
    bulan: int,
    tahun: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_guru),
):
    if bulan < 1 or bulan > 12:
        raise HTTPException(status_code=400, detail="Parameter bulan harus 1-12")
    if tahun < 2000 or tahun > 3000:
        raise HTTPException(status_code=400, detail="Parameter tahun tidak valid")

    rows = (
        db.query(models.Presensi, models.Siswa)
        .join(models.Siswa, models.Presensi.siswa_id == models.Siswa.id)
        .filter(
            and_(
                models.Siswa.kelas == kelas,
                func.strftime("%m", models.Presensi.waktu_scan) == f"{bulan:02d}",
                func.strftime("%Y", models.Presensi.waktu_scan) == str(tahun),
            )
        )
        .order_by(models.Presensi.waktu_scan.asc())
        .all()
    )

    items = [
        schemas.GuruExportPresensiItem(
            siswa_id=siswa.id,
            nama=siswa.nama,
            kelas=siswa.kelas,
            waktu_scan=presensi.waktu_scan,
            status=presensi.status.value,
            keterangan=presensi.keterangan,
        )
        for presensi, siswa in rows
    ]

    return schemas.GuruExportPresensiBulananResponse(
        kelas=kelas,
        bulan=bulan,
        tahun=tahun,
        total_data=len(items),
        data=items,
    )


@app.get("/siswa/my-history", response_model=list[schemas.SiswaHistoryItem])
def siswa_my_history(
    siswa: models.Siswa = Depends(get_current_siswa_jwt),
    db: Session = Depends(get_db),
):
    batas_waktu = datetime.now() - timedelta(days=30)
    presensi_data = (
        db.query(models.Presensi)
        .filter(
            and_(
                models.Presensi.siswa_id == siswa.id,
                models.Presensi.waktu_scan >= batas_waktu,
            )
        )
        .order_by(models.Presensi.waktu_scan.desc())
        .all()
    )

    return [
        schemas.SiswaHistoryItem(
            id=item.id,
            waktu_scan=item.waktu_scan,
            status=item.status.value,
            keterangan=item.keterangan,
        )
        for item in presensi_data
    ]


@app.get("/siswa/notification-data", response_model=schemas.SiswaTodayNotificationOut)
def siswa_notification_data(
    siswa: models.Siswa = Depends(get_current_siswa_jwt),
    db: Session = Depends(get_db),
):
    today = datetime.now().date()
    latest_today = (
        db.query(models.Presensi)
        .filter(
            and_(
                models.Presensi.siswa_id == siswa.id,
                func.date(models.Presensi.waktu_scan) == today,
            )
        )
        .order_by(models.Presensi.waktu_scan.desc())
        .first()
    )

    if latest_today:
        return schemas.SiswaTodayNotificationOut(
            siswa_id=siswa.id,
            nama=siswa.nama,
            kelas=siswa.kelas,
            sudah_scan_hari_ini=True,
            jam_scan=latest_today.waktu_scan,
            status=latest_today.status.value,
            pesan="Presensi hari ini sudah tercatat.",
        )

    return schemas.SiswaTodayNotificationOut(
        siswa_id=siswa.id,
        nama=siswa.nama,
        kelas=siswa.kelas,
        sudah_scan_hari_ini=False,
        jam_scan=None,
        status=None,
        pesan="Belum ada scan presensi hari ini.",
    )
