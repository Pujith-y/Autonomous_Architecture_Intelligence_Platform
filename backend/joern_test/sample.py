import os


class Base:
    pass


class User(Base):

    name: str = "Pujith"

    def __init__(self, value):
        self.value = value

    def get_user(self):
        helper()


def helper():
    pass