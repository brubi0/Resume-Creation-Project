const PHASES = [
  "Profile",
  "Review",
  "Interview",
  "Resume",
  "Prep",
  "Skills",
  "Score",
];

interface Props {
  currentPhase: number;
}

export default function PhaseIndicator({ currentPhase }: Props) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto px-4 py-2">
      {PHASES.map((name, i) => {
        const isActive = i === currentPhase;
        const isDone = i < currentPhase;
        return (
          <div key={name} className="flex items-center">
            {i > 0 && (
              <div
                className={`mx-1 h-0.5 w-4 ${isDone ? "bg-brand-green" : "bg-gray-300"}`}
              />
            )}
            <div
              className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition ${
                isActive
                  ? "bg-brand-dark text-white"
                  : isDone
                    ? "bg-brand-green/20 text-brand-green"
                    : "bg-gray-100 text-gray-400"
              }`}
            >
              {isDone && <span>&#10003;</span>}
              {name}
            </div>
          </div>
        );
      })}
    </div>
  );
}
