from fastapi import HTTPException, Request, Depends

def require_group(group_name: str):
    def checker(request: Request):
        user = request.state.user
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized: missing token")

        groups = user.get("cognito:groups", [])
        if group_name not in groups:
            raise HTTPException(status_code=403, detail="Forbidden: missing permissions")
        return user
    return checker
