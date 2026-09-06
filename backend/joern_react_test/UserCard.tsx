import React, { useState } from "react";

type User = {
    id: number;
    name: string;
};

interface UserCardProps {
    user: User;
}

export function UserCard({
    user,
}: UserCardProps) {

    const [selected, setSelected] =
        useState(false);

    const handleClick = () => {
        setSelected(true);
        console.log(user.name);
    };

    return (
        <div onClick={handleClick}>
            <h1>{user.name}</h1>

            {selected && (
                <span>Selected</span>
            )}
        </div>
    );
}