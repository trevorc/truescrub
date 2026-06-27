import {useEffect, useState} from "react";
import {client} from "client/api/truescrub.js";
import {Accolade} from "proto/highlights_service_pb.js";
import {AccoladeCard} from "client/components/AccoladeCard.js";

const CHICKENS = [
  '/htdocs/img/chicken_ui.png',
  '/htdocs/img/chicken_ui2.png',
  '/htdocs/img/chicken_ui3.png',
  '/htdocs/img/chicken_ui4.png',
  '/htdocs/img/chicken_ui5.png'
];

function getRandomChicken(): string {
  return CHICKENS[Math.floor(Math.random() * CHICKENS.length)];
}

export function AccoladesPage() {
  const [matchDays, setMatchDays] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [accolades, setAccolades] = useState<Accolade[]>([]);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<boolean>(false);
  const [initError, setInitError] = useState<boolean>(false);

  useEffect(() => {
    async function init() {
      try {
        const res = await client.listMatchDays({timezone: "-05:00"});
        const days = res.matchDays.map(d => {
          const m = String(d.month).padStart(2, '0');
          const day = String(d.day).padStart(2, '0');
          return `${d.year}-${m}-${day}`;
        });

        if (days.length === 0) {
          setLoading(false);
          return;
        }

        setMatchDays(days);
        const hash = window.location.hash.substring(1);
        const hashIndex = days.indexOf(hash);
        if (hashIndex !== -1) {
          setCurrentIndex(hashIndex);
        } else {
          setCurrentIndex(0);
        }
      } catch (err) {
        console.error("Failed to load match days:", err);
        setInitError(true);
        setLoading(false);
      }
    }

    init();
  }, []);

  useEffect(() => {
    if (matchDays.length === 0) return;

    const dayString = matchDays[currentIndex];
    window.history.replaceState(null, '', '#' + dayString);

    async function fetchHighlights() {
      setLoading(true);
      setError(false);
      setAccolades([]);

      const splitted = dayString.split('-');
      try {
        const res = await client.getDailyHighlights({
          date: {
            year: parseInt(splitted[0], 10),
            month: parseInt(splitted[1], 10),
            day: parseInt(splitted[2], 10)
          },
          timezone: "-05:00",
          includeAccolades: true,
        });

        setAccolades(res.accolades);
      } catch (err) {
        console.error("Failed to fetch highlights:", err);
        setError(true);
      } finally {
        setLoading(false);
      }
    }

    fetchHighlights();
  }, [currentIndex, matchDays]);

  const hasNoDays = matchDays.length === 0;
  const currentDayString = !hasNoDays ? matchDays[currentIndex] : null;
  const displayDate = currentDayString
      ? new Date(currentDayString + 'T00:00:00-05:00').toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
      : (initError ? "Error" : "No Match Days Found");

  return (
      <>
        <div
            className="flex justify-between items-center mb-8 bg-dark-card p-4 rounded-xl border border-dark-border">
          <button
              onClick={() => setCurrentIndex(i => i + 1)}
              disabled={hasNoDays || currentIndex >= matchDays.length - 1}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            &larr; Previous Match Day
          </button>
          <div className="text-xl font-bold text-brand-400">
            {displayDate}
          </div>
          <button
              onClick={() => setCurrentIndex(i => i - 1)}
              disabled={hasNoDays || currentIndex <= 0}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Next Match Day &rarr;
          </button>
        </div>

        {loading && (
            <div className="text-center py-12 text-slate-400">
              <div className="flex flex-col items-center">
                <img src={getRandomChicken()} className="w-16 h-16 object-contain mb-4"
                     alt="Loading..."
                     style={{animation: "chickenBounce 0.6s ease-in-out infinite alternate"}}/>
                <p>Chickens are crunching the stats...</p>
              </div>
              <style>{`
                @keyframes chickenBounce {
                  0% { transform: translateY(0) rotate(-5deg); }
                  100% { transform: translateY(-12px) rotate(5deg); }
                }
              `}</style>
            </div>
        )}

        {error && !loading && (
            <div className="text-center py-12 text-red-400">
              <p>Failed to load accolades. Please try again later.</p>
            </div>
        )}

        {!loading && !error && accolades.length === 0 && !hasNoDays && (
            <div className="text-center py-16 text-slate-400">
              <img src={getRandomChicken()} className="w-32 h-32 object-contain mx-auto mb-4"
                   alt="No data"/>
              <p className="text-lg font-medium">No accolades available for this day.</p>
              <p className="text-sm text-slate-500 mt-1">Even the chickens left.</p>
            </div>
        )}

        {!loading && !error && accolades.length > 0 && (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
              {accolades.map((acc) => (
                  <AccoladeCard key={`${acc.playerName}-${acc.accolade}`} accolade={acc}/>
              ))}
            </div>
        )}
      </>
  );
}
