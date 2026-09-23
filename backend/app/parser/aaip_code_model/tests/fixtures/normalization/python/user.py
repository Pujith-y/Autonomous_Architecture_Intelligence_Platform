from base import BaseUser


class User(BaseUser):

    name: str

    def get_name(self):
        return self.name