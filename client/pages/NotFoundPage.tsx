import React, {useMemo} from 'react';
import {Link} from 'react-router-dom';

import chicken1 from './chickens/404_chicken_1.png';
import chicken2 from './chickens/404_chicken_2.png';
import chicken3 from './chickens/404_chicken_3.png';

const CHICKENS = [chicken1, chicken2, chicken3];

const MESSAGES = [
  "A chicken ate this page!",
  "Bomb planted at wrong bombsite!",
  "Cluck cluck... nothing here!",
  "This page is currently defusing...",
  "Rush B? More like rush 404.",
];

export function NotFoundPage() {
  const chickenSrc = useMemo(() => {
    return CHICKENS[Math.floor(Math.random() * CHICKENS.length)];
  }, []);

  const message = useMemo(() => {
    return MESSAGES[Math.floor(Math.random() * MESSAGES.length)];
  }, []);

  return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
        <img
            src={chickenSrc}
            alt="Confused Chicken"
            className="w-64 h-64 object-contain mb-8"
        />
        <h1 className="text-4xl font-bold text-gray-800 dark:text-gray-100 mb-4">
          404 - {message}
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400 mb-8">
          We couldn't find the page you were looking for.
        </p>
        <Link
            to="/"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors shadow-sm"
        >
          Rematch
        </Link>
      </div>
  );
}
