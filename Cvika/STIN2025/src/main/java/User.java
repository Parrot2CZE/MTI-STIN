public class User {

    private String username;
    private String password;

    public User(String username, String password) {
        this.username = username;
        setPassword(password);
    }
    public String getUsername() {
        return username;
    }
    public void setUsername(String username) {
        this.username = username;
    }
    public boolean checkPassword(String input) {
        if (input == null) {
            return false;
        }
        return input.equals(this.password);
    }

        private void setPassword(String password) {
        if (!isValidPassword(password)) {
            throw new IllegalArgumentException("Neplatné heslo. Musí mít alespoň 8 znaků a nesmí být null.");
        }
        this.password = password;
    }

    private boolean isValidPassword(String password) {
        if (password == null) {
            return false;
        }
        return password.length() >= 8;
    }
    public boolean changePassword(String oldPassword, String newPassword) {

        if (!checkPassword(oldPassword)) {
            return false;
        }
        if (!isValidPassword(newPassword)) {
            return false;
        }

        this.password = newPassword;
        return true;
    }
}
