import { BaseUser } from "./base";
import { Repository } from "./repository";

export class User extends BaseUser implements Repository {
    save(): void {
    }
}