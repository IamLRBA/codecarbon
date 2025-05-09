from contextlib import AbstractContextManager
from typing import Callable, List
from uuid import UUID

from fastapi import HTTPException

from carbonserver.api.domain.users import Users
from carbonserver.api.infra.database.sql_models import Experiment as SqlModelExperiment
from carbonserver.api.infra.database.sql_models import Membership as SqlModelMembership
from carbonserver.api.infra.database.sql_models import Project as SqlModelProject
from carbonserver.api.infra.database.sql_models import User as SqlModelUser
from carbonserver.api.schemas import User, UserAutoCreate


class SqlAlchemyRepository(Users):
    def __init__(self, session_factory) -> Callable[..., AbstractContextManager]:
        self.session_factory = session_factory

    def create_user(self, user: UserAutoCreate) -> User:
        """Creates a user in the database
        :returns: A User in pyDantic BaseModel format.
        :rtype: schemas.User
        """
        with self.session_factory() as session:
            db_user = SqlModelUser(
                id=user.id,
                name=user.name,
                email=user.email,
                is_active=True,
                organizations=[],
            )
            session.add(db_user)
            session.commit()
            session.refresh(db_user)
            return self.map_sql_to_schema(db_user)

    def get_user_by_id(self, user_id: UUID) -> User:
        """Find an user in database and retrieves it

        :user_id: The id of the user to retrieve.
        :returns: An User in pyDantic BaseModel format.
        :rtype: schemas.User
        """
        with self.session_factory() as session:
            e = session.query(SqlModelUser).filter(SqlModelUser.id == user_id).first()
            if e is None:
                raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            return self.map_sql_to_schema(e)

    def get_user_by_email(self, email: str) -> User:
        """Find an user in database and retrieves it

        :email: The email of the user to retrieve.
        :returns: An User in pyDantic BaseModel format.
        :rtype: schemas.User
        """
        with self.session_factory() as session:
            e = session.query(SqlModelUser).filter(SqlModelUser.email == email).first()
            if e is None:
                raise HTTPException(status_code=404, detail=f"User {email} not found")
            return self.map_sql_to_schema(e)

    def list_users(self) -> List[User]:
        with self.session_factory() as session:
            e = session.query(SqlModelUser)
            if e is None:
                return None
            users: List[User] = []
            for user in e:
                users.append(self.map_sql_to_schema(user))
            return users

    def subscribe_user_to_org(
        self,
        user: User,
        organization_id: UUID,
    ) -> None:
        with self.session_factory() as session:
            e = (
                session.query(SqlModelMembership)
                .filter(SqlModelMembership.user_id == user.id)
                .filter(SqlModelMembership.organization_id == organization_id)
                .first()
            )
            if e is not None:
                return

            db_membership = SqlModelMembership(
                user_id=user.id,
                organization_id=organization_id,
                is_admin=True,
            )
            session.add(db_membership)
            session.commit()
            return user

    def is_user_in_organization(
        self, organization_id: UUID, user: User, *, is_admin: bool | None = None
    ):
        if user is None:
            return False
        with self.session_factory() as session:
            e = (
                session.query(SqlModelMembership)
                .filter(SqlModelMembership.user_id == user.id)
                .filter(SqlModelMembership.organization_id == organization_id)
            )
            if is_admin is not None:
                e = e.filter(SqlModelMembership.is_admin == is_admin)
            return e.first() is not None

    def is_admin_in_organization(self, organization_id: UUID, user: User):
        return self.is_user_in_organization(organization_id, user, is_admin=True)

    def is_user_authorized_on_project(self, project_id, user_id: UUID):
        with self.session_factory() as session:
            e = (
                session.query(SqlModelMembership)
                .join(
                    SqlModelProject,
                    SqlModelProject.id == project_id,
                )
                .filter(SqlModelMembership.user_id == user_id)
                .filter(
                    SqlModelMembership.organization_id
                    == SqlModelProject.organization_id
                )
                .first()
            )
            return e is not None

    def is_user_authorized_on_experiment(self, experiment_id, user_id: UUID):
        with self.session_factory() as session:
            e = (
                session.query(SqlModelMembership)
                .join(
                    SqlModelExperiment,
                    SqlModelExperiment.id == experiment_id,
                )
                .join(
                    SqlModelProject,
                    SqlModelProject.id == SqlModelExperiment.project_id,
                )
                .filter(SqlModelMembership.user_id == user_id)
                .filter(SqlModelExperiment.id == experiment_id)
                .filter(
                    SqlModelMembership.organization_id
                    == SqlModelProject.organization_id
                )
                .first()
            )
            return e is not None

    @staticmethod
    def map_sql_to_schema(sql_user: SqlModelUser) -> User:
        """Sql To Pydantic Mapper

        :returns: An User in pyDantic BaseModel format.
        :rtype: schemas.User
        """
        return User(
            id=sql_user.id,
            name=sql_user.name,
            email=sql_user.email,
            is_active=sql_user.is_active,
            organizations=[m.organization_id for m in sql_user.organizations],
        )
