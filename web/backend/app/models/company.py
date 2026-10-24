from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Company(Base):
    """Empresa atendida pelo sistema. Funcionários, feriados, admins e auditoria pertencem a uma empresa."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # Aviso de privacidade (LGPD): a quem o funcionário pede acesso ou correção dos dados
    privacy_contact: Mapped[str] = mapped_column(String, default="", server_default="")
    # Empresa desativada: os admins dela não entram, os relógios e os celulares param
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"))
    # Assina os relógios da empresa; trocar desliga todos eles de uma vez
    kiosk_secret: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
