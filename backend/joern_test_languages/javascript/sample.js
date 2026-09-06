class Base {
}

class User extends Base {

    constructor(name) {
        this.name = name;
    }

    getUser() {
        return this.name;
    }
}

function helper() {
    return "hello";
}