# ==========================================
# SIMPLE INHERITANCE
# ==========================================

class Animal:
    def speak(self):
        return "sound"


class Dog(Animal):
    def bark(self):
        return "woof"


# ==========================================
# MULTI-LEVEL INHERITANCE
# ==========================================

class Vehicle:
    pass


class Car(Vehicle):
    pass


class ElectricCar(Car):
    def charge(self):
        return "charging"


# ==========================================
# MULTIPLE INHERITANCE
# ==========================================

class Flyable:
    pass


class Swimmable:
    pass


class Duck(Flyable, Swimmable):
    def move(self):
        return "moving"


# ==========================================
# TOP-LEVEL FUNCTION
# Should NOT belong to a class
# ==========================================

def helper():
    return "helper"


# ==========================================
# NESTED CLASS
# Tests longest matching class ownership
# ==========================================

class Outer:

    def outer_method(self):
        return "outer"

    class Inner:

        def inner_method(self):
            return "inner"


# ==========================================
# CLASS WITH NO METHODS
# ==========================================

class EmptyClass:
    pass