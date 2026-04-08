import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from database import Base


class UserRole(str, enum.Enum):
    ADMIN = "Admin"
    GURU = "Guru"
    SISWA = "Siswa"


class StatusPresensi(str, enum.Enum):
    HADIR = "Hadir"
    TERLAMBAT = "Terlambat"
    ALPA = "Alpa"
    IZIN = "Izin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    # Menyimpan password yang sudah di-hash, bukan plain text.
    password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)

    siswa_profile = relationship("Siswa", back_populates="user", uselist=False)
    guru_profile = relationship("Guru", back_populates="user", uselist=False)


class Siswa(Base):
    __tablename__ = "siswa"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    uid_rfid = Column(String(100), unique=True, nullable=False, index=True)
    nama = Column(String(150), nullable=False)
    kelas = Column(String(50), nullable=False)
    no_ortu = Column(String(30), nullable=False)

    user = relationship("User", back_populates="siswa_profile")
    presensi = relationship("Presensi", back_populates="siswa")


class Guru(Base):
    __tablename__ = "guru"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    nama = Column(String(150), nullable=False)
    nip = Column(String(50), unique=True, nullable=False, index=True)
    mata_pelajaran = Column(String(100), nullable=False)

    user = relationship("User", back_populates="guru_profile")


class Presensi(Base):
    __tablename__ = "presensi"

    id = Column(Integer, primary_key=True, index=True)
    siswa_id = Column(Integer, ForeignKey("siswa.id"), nullable=False)
    waktu_scan = Column(DateTime(timezone=False), server_default=func.now(), nullable=False)
    status = Column(Enum(StatusPresensi), nullable=False)
    keterangan = Column(String(255), nullable=True)

    siswa = relationship("Siswa", back_populates="presensi")


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(String(100), nullable=False)
