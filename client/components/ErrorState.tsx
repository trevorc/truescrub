import {useState} from "react";

import error1 from "client/components/img/chicken_error.png";
import error2 from "client/components/img/chicken_error2.png";
import error3 from "client/components/img/chicken_error3.png";

const ERROR_CHICKENS = [error1, error2, error3];

function getRandomErrorChicken(): string {
  return ERROR_CHICKENS[Math.floor(Math.random() * ERROR_CHICKENS.length)];
}

export function ErrorState({message}: { message?: string }) {
  const [chicken] = useState(getRandomErrorChicken);

  return (
      <div className="text-center py-12 text-red-400">
        <div className="flex flex-col items-center">
          <img src={chicken}
               className="w-32 h-32 object-contain mb-4"
               alt="Error"/>
          <p className="text-lg font-medium">{message ?? "Something went wrong. Please try again later."}</p>
        </div>
      </div>
  );
}
