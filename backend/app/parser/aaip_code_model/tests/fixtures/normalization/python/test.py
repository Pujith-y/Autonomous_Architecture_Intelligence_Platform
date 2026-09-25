from typing import List, Dict, Union, Optional

class User:
    pass

class Admin:
    pass


def get_user() -> User:
    pass


def get_count() -> int:
    pass


def get_users() -> List[User]:
    pass


def get_user_map() -> Dict[str, User]:
    pass


def find_user() -> Optional[User]:
    pass


def get_account() -> Union[User, Admin]:
    pass

def process_user(user: User) -> int:
    pass


def process_users(users: List[User]) -> int:
    pass


def process_account(account: Union[User, Admin]) -> int:
    pass