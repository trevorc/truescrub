import {useState, useEffect} from "react";

const QUIPS = [
  "No chickens were harmed in the making of this leaderboard.",
  "The chickens believe in you. Probably.",
  "Chickens spectate every round. They've seen things.",
  "Fun fact: chickens have a higher survival rate than most players.",
  "The chicken knows your true rank. It judges silently.",
  "Somewhere on Inferno, a chicken just witnessed your whiff.",
  "Powered by free-range matchmaking.",
  "Bawk bawk. That's chicken for 'git gud'.",
  "The chicken remembers every teamkill.",
  "Even the chickens have better crosshair placement.",
];

export function Footer() {
  const [quip, setQuip] = useState("");

  useEffect(() => {
    setQuip(QUIPS[Math.floor(Math.random() * QUIPS.length)]);
  }, []);

  return (
      <footer className="max-w-7xl mx-auto mt-auto pt-16 pb-4 text-center text-slate-500 text-sm">
        <div className="flex items-center justify-center gap-2 mb-1">
          <span
              className="opacity-50 hover:opacity-100 hover:scale-125 transition-all duration-300 cursor-pointer inline-block">
            🐔
          </span>
          <p className="italic">{quip}</p>
        </div>
        <p>&copy; {new Date().getFullYear()} TrueScrub</p>
      </footer>
  );
}
