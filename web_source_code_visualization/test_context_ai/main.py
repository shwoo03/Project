
import auth

def login(user, password):
    if auth.verify_admin(user, password):
        print("Welcome Admin!")
    else:
        print("Access Denied")
