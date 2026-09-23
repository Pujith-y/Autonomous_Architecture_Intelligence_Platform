// ==========================================
// SIMPLE INHERITANCE
// ==========================================

class Animal {

    speak() {
        return "sound";
    }
}


class Dog extends Animal {

    bark() {
        return "woof";
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

    charge() {
        return "charging";
    }
}


// ==========================================
// TOP-LEVEL FUNCTION
// Should NOT belong to a class
// ==========================================

function helper() {
    return "helper";
}


// ==========================================
// NESTED CLASS
// ==========================================

class Outer {

    outerMethod() {
        return "outer";
    }

    static Inner = class {

        innerMethod() {
            return "inner";
        };
    };
}


// ==========================================
// CLASS WITH NO METHODS
// ==========================================

class EmptyClass {
}