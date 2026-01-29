
def verify_admin(user, password):
    # VULNERABILITY: Hardcoded admin password
    if user == "admin" and password == "super_secret_123":
        return True
    return False
