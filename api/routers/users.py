"""
api/routers/users.py — admin user management.

Mirrors admin/dashboard.py::_users_tab exactly: same duplicate-username
check, same self-role-change/self-delete protection.
"""

from fastapi import APIRouter, Depends, HTTPException

from data.db import (
    change_password,
    create_user,
    delete_user,
    force_password_change,
    get_all_users,
    set_user_role,
)

from api.deps import require_admin
from api.schemas import PasswordResetRequest, RoleUpdateRequest, UserCreateRequest, UserOut

router = APIRouter()


@router.get("", response_model=list[UserOut])
def list_users(admin: dict = Depends(require_admin)):
    return get_all_users()


@router.post("", response_model=UserOut)
def create_user_endpoint(body: UserCreateRequest, admin: dict = Depends(require_admin)):
    uname = body.username.strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username required.")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if any(u["username"].lower() == uname.lower() for u in get_all_users()):
        raise HTTPException(status_code=409, detail="Username already exists.")

    new_u = create_user(uname, body.password, body.role, created_by=admin["username"])
    return UserOut(**new_u)


@router.patch("/{user_id}/role")
def update_role(user_id: str, body: RoleUpdateRequest, admin: dict = Depends(require_admin)):
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot change your own role.")
    set_user_role(user_id, body.role)
    return {"ok": True}


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: str, body: PasswordResetRequest, admin: dict = Depends(require_admin)
):
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    change_password(user_id, body.new_password)
    force_password_change(user_id)
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user_endpoint(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    delete_user(user_id)
    return {"ok": True}
