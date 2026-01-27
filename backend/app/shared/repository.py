"""
Base repository with common CRUD operations.

Provides generic database operations for all feature repositories.
Uses SQLAlchemy async session for non-blocking database access.

Usage:
    class UserRepository(BaseRepository[User]):
        def __init__(self, db: AsyncSession):
            super().__init__(db, User)

        async def get_by_telegram_id(self, telegram_id: str) -> User | None:
            return await self.get_by(telegram_id=telegram_id)
"""

from typing import TypeVar, Generic, Type
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """
    Base repository for database operations.

    Provides common CRUD methods that can be inherited by feature repositories.
    All methods are async for use with AsyncSession.
    """

    def __init__(self, db: AsyncSession, model: Type[T]):
        """
        Initialize repository.

        Args:
            db: Async database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model

    async def get_by_id(self, id: str | int) -> T | None:
        """
        Get entity by primary key ID.

        Args:
            id: Primary key value (string UUID or integer)

        Returns:
            Entity if found, None otherwise
        """
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by(self, **kwargs) -> T | None:
        """
        Get single entity by arbitrary field values.

        Args:
            **kwargs: Field name-value pairs to filter by

        Returns:
            First matching entity or None
        """
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, **kwargs) -> list[T]:
        """
        Get all entities matching criteria.

        Args:
            **kwargs: Field name-value pairs to filter by

        Returns:
            List of matching entities
        """
        query = select(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, **kwargs) -> T:
        """
        Create new entity.

        Args:
            **kwargs: Field values for new entity

        Returns:
            Created entity with generated ID
        """
        entity = self.model(**kwargs)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def update(self, entity: T, **kwargs) -> T:
        """
        Update entity fields.

        Args:
            entity: Entity to update
            **kwargs: Field values to update

        Returns:
            Updated entity
        """
        for key, value in kwargs.items():
            setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """
        Delete entity.

        Args:
            entity: Entity to delete
        """
        await self.db.delete(entity)
        await self.db.flush()

    async def count(self, **kwargs) -> int:
        """
        Count entities matching criteria.

        Args:
            **kwargs: Field name-value pairs to filter by

        Returns:
            Number of matching entities
        """
        from sqlalchemy import func
        query = select(func.count()).select_from(self.model)
        for key, value in kwargs.items():
            query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar() or 0
