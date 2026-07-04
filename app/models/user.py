import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    readings: Mapped[list["HealthReading"]] = relationship(back_populates="user")
    healthy_ranges: Mapped[list["HealthyRange"]] = relationship(back_populates="user")


# Resolve forward references after all models are imported.
from app.models.reading import HealthReading  # noqa: E402, F811
from app.models.healthy_range import HealthyRange  # noqa: E402, F811
