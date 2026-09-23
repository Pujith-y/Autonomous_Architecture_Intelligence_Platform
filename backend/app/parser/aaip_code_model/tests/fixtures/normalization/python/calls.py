class User:
    def validate(self):
        pass

    def save(self):
        self.validate()


def save(user: User):
    user.validate()