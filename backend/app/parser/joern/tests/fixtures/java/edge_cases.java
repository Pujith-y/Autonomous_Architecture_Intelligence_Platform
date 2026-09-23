package edgecases;


// ==========================================
// SIMPLE INHERITANCE
// ==========================================

class Animal {

    void speak() {
        System.out.println("sound");
    }
}


class Dog extends Animal {

    void bark() {
        System.out.println("woof");
    }
}


// ==========================================
// MULTI-LEVEL INHERITANCE
// ==========================================

class Vehicle {
}


class Car extends Vehicle {
}


class ElectricCar extends Car {

    void charge() {
        System.out.println("charging");
    }
}


// ==========================================
// INTERFACE
// ==========================================

interface Flyable {

    void fly();
}


class Bird implements Flyable {

    public void fly() {
        System.out.println("flying");
    }
}


// ==========================================
// NESTED CLASS
// ==========================================

class Outer {

    void outerMethod() {
    }


    static class Inner {

        void innerMethod() {
        }
    }
}


// ==========================================
// CLASS WITH NO METHODS
// ==========================================

class EmptyClass {
}