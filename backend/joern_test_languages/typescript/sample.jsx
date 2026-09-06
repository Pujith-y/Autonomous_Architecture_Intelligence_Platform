class Base {
}


class User extends Base {

    name: string;

    constructor(name: string) {
        this.name = name;
    }

    getUser(): string {
        return this.name;
    }
}