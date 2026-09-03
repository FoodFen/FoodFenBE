"""Use-case providers for the user slice."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.application.use_cases.get_user import GetUserUseCase
from src.infrastructure.di import UserRepositoryDep


def get_get_user_use_case(repo: UserRepositoryDep) -> GetUserUseCase:
    return GetUserUseCase(users=repo)


GetUserUseCaseDep = Annotated[GetUserUseCase, Depends(get_get_user_use_case)]
