from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------- User schemas ----------
class UserBase(BaseModel):
    username: str = Field(min_length=3, max_length=100)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: Literal["Admin", "Guru", "Siswa"]


# Role-based input untuk validasi terpisah per level akses
class AdminCreate(UserBase):
    password: str = Field(min_length=8, max_length=255)
    role: Literal["Admin"] = "Admin"


class GuruCreate(UserBase):
    password: str = Field(min_length=8, max_length=255)
    role: Literal["Guru"] = "Guru"


class SiswaCreate(UserBase):
    password: str = Field(min_length=8, max_length=255)
    role: Literal["Siswa"] = "Siswa"


# ---------- Siswa schemas ----------
class SiswaBase(BaseModel):
    uid_rfid: str = Field(min_length=1, max_length=100)
    nama: str = Field(min_length=1, max_length=150)
    kelas: str = Field(min_length=1, max_length=50)
    no_ortu: str = Field(min_length=8, max_length=30)


class SiswaProfileCreate(SiswaBase):
    user_id: int


class SiswaProfileOut(SiswaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


# ---------- Guru schemas ----------
class GuruBase(BaseModel):
    nama: str = Field(min_length=1, max_length=150)
    nip: str = Field(min_length=1, max_length=50)
    mata_pelajaran: str = Field(min_length=1, max_length=100)


class GuruProfileCreate(GuruBase):
    user_id: int


class GuruProfileOut(GuruBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


# ---------- Presensi schemas ----------
class PresensiBase(BaseModel):
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = Field(default=None, max_length=255)


class PresensiCreate(PresensiBase):
    siswa_id: int


class PresensiOut(PresensiBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    siswa_id: int
    waktu_scan: datetime


# ---------- RFID Scan schemas ----------
class RFIDScanRequest(BaseModel):
    uid_rfid: str = Field(min_length=1, max_length=100)


class RFIDScanResponse(BaseModel):
    nama_siswa: str
    jam_scan: datetime
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]


# ---------- Admin management schemas ----------
class AdminSiswaCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=255)
    uid_rfid: str = Field(min_length=1, max_length=100)
    nama: str = Field(min_length=1, max_length=150)
    kelas: str = Field(min_length=1, max_length=50)
    no_ortu: str = Field(min_length=8, max_length=30)


class AdminSiswaUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=255)
    uid_rfid: Optional[str] = Field(default=None, min_length=1, max_length=100)
    nama: Optional[str] = Field(default=None, min_length=1, max_length=150)
    kelas: Optional[str] = Field(default=None, min_length=1, max_length=50)
    no_ortu: Optional[str] = Field(default=None, min_length=8, max_length=30)


class AdminSiswaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    uid_rfid: str
    nama: str
    kelas: str
    no_ortu: str


class AdminGuruCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=255)
    nama: str = Field(min_length=1, max_length=150)
    nip: str = Field(min_length=1, max_length=50)
    mata_pelajaran: str = Field(min_length=1, max_length=100)


class AdminGuruUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=255)
    nama: Optional[str] = Field(default=None, min_length=1, max_length=150)
    nip: Optional[str] = Field(default=None, min_length=1, max_length=50)
    mata_pelajaran: Optional[str] = Field(default=None, min_length=1, max_length=100)


class AdminGuruOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: str
    nama: str
    nip: str
    mata_pelajaran: str


class AdminStatsOut(BaseModel):
    hadir: int
    terlambat: int
    alpa: int


class AttendanceConfigUpdate(BaseModel):
    hadir_batas: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")
    terlambat_batas: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d:[0-5]\d$")


class AttendanceConfigOut(BaseModel):
    hadir_batas: str
    terlambat_batas: str


# ---------- Guru dashboard schemas ----------
class GuruKelasPresensiItem(BaseModel):
    siswa_id: int
    nama: str
    kelas: str
    jam_scan: Optional[datetime] = None
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = None


class GuruManualOverrideRequest(BaseModel):
    siswa_id: int
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = Field(default=None, max_length=255)


class GuruManualOverrideResponse(BaseModel):
    siswa_id: int
    nama: str
    kelas: str
    jam_scan: datetime
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = None


class GuruExportPresensiItem(BaseModel):
    siswa_id: int
    nama: str
    kelas: str
    waktu_scan: datetime
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = None


class GuruExportPresensiBulananResponse(BaseModel):
    kelas: str
    bulan: int
    tahun: int
    total_data: int
    data: list[GuruExportPresensiItem]


# ---------- Auth & Siswa Mobile schemas ----------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: Literal["Admin", "Guru", "Siswa"]


class SiswaHistoryItem(BaseModel):
    id: int
    waktu_scan: datetime
    status: Literal["Hadir", "Terlambat", "Alpa", "Izin"]
    keterangan: Optional[str] = None


class SiswaTodayNotificationOut(BaseModel):
    siswa_id: int
    nama: str
    kelas: str
    sudah_scan_hari_ini: bool
    jam_scan: Optional[datetime] = None
    status: Optional[Literal["Hadir", "Terlambat", "Alpa", "Izin"]] = None
    pesan: str
