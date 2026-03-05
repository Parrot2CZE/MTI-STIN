public class Main {
    public static void main(String[] args) {
        User validUser = new User("alice", "tajneheslo"); // 11 znaků → OK
        System.out.println("Uživatel vytvořen: " + validUser.getUsername());

        // 2) Pokus o vytvoření s neplatným heslem
        try {
            User invalidUser = new User("bob", "kratke"); // 6 znaků → neplatné
            System.out.println("Tento řádek by se neměl nikdy vypsat.");
        } catch (IllegalArgumentException e) {
            System.out.println("Nepodařilo se vytvořit uživatele: " + e.getMessage());
        }

        // 3) Ukázka ověření hesla
        boolean correct = validUser.checkPassword("tajneheslo");
        boolean incorrect = validUser.checkPassword("spatneheslo");

        System.out.println("Správné heslo: " + correct);   // true
        System.out.println("Špatné heslo: " + incorrect);   // false

        // 4) Bonus: změna hesla
        boolean changedOk = validUser.changePassword("tajneheslo", "noveHeslo123");
        System.out.println("Změna hesla (správné staré heslo): " + changedOk); // true

        boolean changedFail = validUser.changePassword("spatneHeslo", "dalsiHeslo123");
        System.out.println("Změna hesla (špatné staré heslo): " + changedFail); // false
    }
}
