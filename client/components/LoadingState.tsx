import {useState} from "react";

import chicken1 from "client/components/chickens/chicken_ui.png";
import chicken2 from "client/components/chickens/chicken_ui2.png";
import chicken3 from "client/components/chickens/chicken_ui3.png";
import chicken4 from "client/components/chickens/chicken_ui4.png";
import chicken5 from "client/components/chickens/chicken_ui5.png";
import chicken6 from "client/components/chickens/chicken_ui6.png";
import chicken7 from "client/components/chickens/chicken_ui7.png";

const LOADING_CHICKENS = [chicken1, chicken2, chicken3, chicken4, chicken5, chicken6, chicken7];

const CHICKEN_FACTS = [
  "The chicken doesn't peek mid. Mid peeks the chicken.",
  "The chicken once clutched a 1v5. While AFK.",
  "The chicken knows exactly which angle you are holding.",
  "When the chicken throws a smoke, it blocks the server's vision.",
  "The chicken doesn't need Kevlar. Bullets need Kevlar from the chicken.",
  "The chicken doesn't bypass VAC. VAC uninstalls itself out of respect.",
  "When the chicken gets a network timeout, it just recalculates the entire game state from first principles.",
  "The chicken thinks you should buy a P90 and rush B. The chicken is always right.",
  "The chicken is currently experiencing a crisis of faith regarding the economy.",
  "The chicken thinks you should save this round. And every round. Just in case.",
];

function getRandomLoadingChicken(): string {
  return LOADING_CHICKENS[Math.floor(Math.random() * LOADING_CHICKENS.length)];
}

function getRandomFact(): string {
  return CHICKEN_FACTS[Math.floor(Math.random() * CHICKEN_FACTS.length)];
}

export function LoadingState({message}: { message?: string }) {
  const [chicken] = useState(getRandomLoadingChicken);
  const [fact] = useState(getRandomFact);

  return (
      <div className="text-center py-12 text-slate-400">
        <div className="flex flex-col items-center">
          <img src={chicken}
               className="w-16 h-16 object-contain mb-4 animate-chickenBounce"
               alt="Loading..."/>
          <p className="animate-pulse text-lg mb-2">{message ?? "Loading..."}</p>
          <p className="text-sm text-slate-500 italic max-w-md mx-auto">{fact}</p>
        </div>
      </div>
  );
}
