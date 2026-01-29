
public class UserManager {
    public void createUser(String name, int age) {
        System.out.println("Creating user " + name);
    }

    public User getUser(int id) {
        return new User(id);
    }
}
