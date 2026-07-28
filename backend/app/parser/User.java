package com.aaip.parser;
import java.util.random;

public class User extends Admin{
    public UserRepository repo = new UserRepository();
    public final int num = 0;
    public void login() {
        int ki = 0;
        UserRepository repo = new UserRepository();
        AuthService auth = new AuthService();
        System.out.println("Hello");
        validate();
        credentials();
    }

    public void validate(){
        credentials();
    }

    public void credentials(){
    }

}

class Admin implements Serializable, Cloneable {
}