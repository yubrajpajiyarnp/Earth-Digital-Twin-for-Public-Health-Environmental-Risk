from fastapi import Header, HTTPException

# Deliberately NOT real authentication, per explicit request: whoever sends this exact
# email string in the X-Admin-Email header gets full admin access — no password, no
# token, no verification that the caller actually owns this inbox. Anyone reading the
# frontend source or a network request can see this value and self-declare as admin.
# Acceptable ONLY because this app is not deployed anywhere reachable by anyone else;
# revisit before ever exposing this beyond localhost. See CLAUDE.md.
ADMIN_EMAIL = "yubraj2k05@gmail.com"


def require_admin(x_admin_email: str | None = Header(default=None)) -> str:
    if x_admin_email != ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return x_admin_email
