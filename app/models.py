from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import relationship

from .database import base


class UserRole(base):
    __tablename__ = "user_role"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


class RequestStatus(base):
    __tablename__ = "request_status"

    id = Column(Integer, primary_key=True)
    name = Column(String(60), unique=True, nullable=False)
    is_final = Column(Boolean, nullable=False, default=False)


class EquipmentType(base):
    __tablename__ = "equipment_type"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)

    models = relationship("EquipmentModel", back_populates="equipment_type")


class EquipmentModel(base):
    __tablename__ = "equipment_model"
    __table_args__ = (
        UniqueConstraint("equipment_type_id", "name", name="uq_equipment_model_type_name"),
    )

    id = Column(Integer, primary_key=True)
    equipment_type_id = Column(Integer, ForeignKey("equipment_type.id"), nullable=False)
    name = Column(String(200), nullable=False)

    equipment_type = relationship("EquipmentType", back_populates="models")
    requests = relationship("RepairRequest", back_populates="equipment_model")


class IssueType(base):
    __tablename__ = "issue_type"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)

    requests = relationship("RepairRequest", back_populates="issue_type")


class User(base):
    __tablename__ = "app_user"

    id = Column(Integer, primary_key=True)
    fio = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    login = Column(String(60), unique=True, nullable=False)
    password_hash = Column(String(300), nullable=False)
    role_id = Column(Integer, ForeignKey("user_role.id"), nullable=False)

    role = relationship("UserRole")

    client_requests = relationship(
        "RepairRequest",
        back_populates="client",
        foreign_keys="RepairRequest.client_id",
    )
    master_requests = relationship(
        "RepairRequest",
        back_populates="master",
        foreign_keys="RepairRequest.master_id",
    )
    comments = relationship(
        "RequestComment",
        back_populates="master",
        foreign_keys="RequestComment.master_id",
    )


class RepairRequest(base):
    __tablename__ = "repair_request"

    id = Column(Integer, primary_key=True)
    start_date = Column(Date, nullable=False)

    equipment_model_id = Column(Integer, ForeignKey("equipment_model.id"), nullable=False)
    issue_type_id = Column(Integer, ForeignKey("issue_type.id"), nullable=False)

    problem_description = Column(Text, nullable=False)

    status_id = Column(Integer, ForeignKey("request_status.id"), nullable=False)
    completion_date = Column(Date, nullable=True)

    repair_parts = Column(Text, nullable=True)

    master_id = Column(Integer, ForeignKey("app_user.id"), nullable=True)
    client_id = Column(Integer, ForeignKey("app_user.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    equipment_model = relationship("EquipmentModel", back_populates="requests")
    issue_type = relationship("IssueType", back_populates="requests")
    status = relationship("RequestStatus")

    master = relationship("User", foreign_keys=[master_id], back_populates="master_requests")
    client = relationship("User", foreign_keys=[client_id], back_populates="client_requests")

    comments = relationship(
        "RequestComment",
        back_populates="request",
        cascade="all, delete-orphan",
    )


class RequestComment(base):
    __tablename__ = "request_comment"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("repair_request.id", ondelete="CASCADE"), nullable=False)
    master_id = Column(Integer, ForeignKey("app_user.id"), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    request = relationship("RepairRequest", back_populates="comments")
    master = relationship("User", back_populates="comments")