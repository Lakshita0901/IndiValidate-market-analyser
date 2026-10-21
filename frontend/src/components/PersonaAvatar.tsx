import React from 'react';

interface PersonaAvatarProps {
  seed: string;
  name?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
}

// Consistent seed hasher to select deterministic visual traits
function hashSeed(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export const PersonaAvatar: React.FC<PersonaAvatarProps> = ({
  seed,
  name = '',
  size = 'md',
  className = '',
}) => {
  const hash = hashSeed(seed + (name || ''));

  // Trait selections based on hash
  const skinTones = ['#F5D0C5', '#E8B49F', '#D69B82', '#FCE1D4', '#C98263'];
  const hairColors = ['#2C1A1D', '#542227', '#873F46', '#4A3B32', '#7A4839', '#3A2E2B'];
  const bgColors = ['#F4E9E7', '#EAE0DE', '#EDF6F0', '#FAF2EA', '#EFE6E8'];
  const shirtColors = ['#873F46', '#B66B70', '#3E7B54', '#5A464B', '#C06E22', '#6D2F35'];

  const skin = skinTones[hash % skinTones.length];
  const hairColor = hairColors[(hash >> 2) % hairColors.length];
  const bg = bgColors[(hash >> 4) % bgColors.length];
  const shirt = shirtColors[(hash >> 6) % shirtColors.length];
  const hairStyle = (hash >> 8) % 5;
  const hasGlasses = (hash >> 10) % 3 === 0;
  const hasFacialHair = (hash >> 12) % 4 === 0;
  const accessory = (hash >> 14) % 4; // 0=none, 1=badge/pin, 2=collar/tie, 3=headset

  const sizeDimensions = {
    sm: 'w-9 h-9',
    md: 'w-13 h-13',
    lg: 'w-18 h-18',
    xl: 'w-24 h-24',
  };

  const dim = sizeDimensions[size];

  return (
    <div
      className={`relative rounded-2xl overflow-hidden shrink-0 border border-[#E7DAD8] shadow-xs flex items-center justify-center ${dim} ${className}`}
      style={{ backgroundColor: bg }}
      title={`Synthetic illustrated avatar for ${name || seed}`}
    >
      <svg
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        {/* Soft background radial wash */}
        <circle cx="50" cy="50" r="48" fill={bg} />

        {/* Torso / Clothes */}
        <path
          d="M20 98 C20 74 34 68 50 68 C66 68 80 74 80 98 Z"
          fill={shirt}
        />
        {/* Collar / Lapel accent */}
        <path
          d="M42 68 L50 82 L58 68 Z"
          fill="#FFFFFF"
          opacity="0.85"
        />

        {accessory === 2 && (
          /* Small Tie */
          <path d="M48 76 L52 76 L54 94 L50 97 L46 94 Z" fill="#542227" />
        )}

        {/* Neck */}
        <rect x="44" y="56" width="12" height="15" rx="3" fill={skin} />

        {/* Head Base */}
        <ellipse cx="50" cy="44" rx="20" ry="24" fill={skin} />

        {/* Ears */}
        <ellipse cx="30" cy="45" rx="3.5" ry="6" fill={skin} />
        <ellipse cx="70" cy="45" rx="3.5" ry="6" fill={skin} />

        {/* Hair Styles */}
        {hairStyle === 0 && (
          /* Short cropped / tapered */
          <path
            d="M30 40 C30 24 38 20 50 20 C62 20 70 24 70 40 C66 30 60 27 50 27 C40 27 34 30 30 40 Z"
            fill={hairColor}
          />
        )}

        {hairStyle === 1 && (
          /* Wavy / voluminous */
          <g fill={hairColor}>
            <circle cx="35" cy="28" r="10" />
            <circle cx="50" cy="24" r="11" />
            <circle cx="65" cy="28" r="10" />
            <path d="M28 42 C28 26 38 22 50 22 C62 22 72 26 72 42 C68 33 62 30 50 30 C38 30 32 33 28 42 Z" />
          </g>
        )}

        {hairStyle === 2 && (
          /* Sleek side part */
          <path
            d="M28 44 C28 22 40 18 54 18 C68 18 72 26 72 44 C67 33 60 28 48 26 C36 24 30 32 28 44 Z"
            fill={hairColor}
          />
        )}

        {hairStyle === 3 && (
          /* Long bob / shoulder length framing */
          <g fill={hairColor}>
            <path d="M29 38 C29 22 40 19 50 19 C60 19 71 22 71 38 C71 58 68 62 67 64 C65 52 64 32 50 32 C36 32 35 52 33 64 C32 62 29 58 29 38 Z" />
          </g>
        )}

        {hairStyle === 4 && (
          /* Topknot / bun */
          <g fill={hairColor}>
            <ellipse cx="50" cy="16" rx="8" ry="7" />
            <path d="M30 40 C30 24 38 21 50 21 C62 21 70 24 70 40 C66 31 60 28 50 28 C40 28 34 31 30 40 Z" />
          </g>
        )}

        {/* Eyes */}
        <circle cx="42" cy="44" r="2.2" fill="#302629" />
        <circle cx="58" cy="44" r="2.2" fill="#302629" />
        {/* Eye highlights */}
        <circle cx="41.3" cy="43.3" r="0.7" fill="#FFFFFF" />
        <circle cx="57.3" cy="43.3" r="0.7" fill="#FFFFFF" />

        {/* Eyebrows */}
        <path d="M39 39 Q42 37 45 39" stroke={hairColor} strokeWidth="1.6" strokeLinecap="round" />
        <path d="M55 39 Q58 37 61 39" stroke={hairColor} strokeWidth="1.6" strokeLinecap="round" />

        {/* Subtle Nose */}
        <path d="M50 44 L48.5 50 L51.5 50" stroke="#B88A7D" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Mouth */}
        <path d="M45 56 Q50 59 55 56" stroke="#873F46" strokeWidth="1.6" strokeLinecap="round" />

        {/* Cheeks */}
        <circle cx="37" cy="49" r="3" fill="#E88B88" opacity="0.4" />
        <circle cx="63" cy="49" r="3" fill="#E88B88" opacity="0.4" />

        {/* Glasses Option */}
        {hasGlasses && (
          <g stroke="#302629" strokeWidth="1.6" fill="none">
            <rect x="36" y="40" width="11" height="9" rx="2.5" />
            <rect x="53" y="40" width="11" height="9" rx="2.5" />
            <line x1="47" y1="44" x2="53" y2="44" />
            <line x1="30" y1="43" x2="36" y2="43" />
            <line x1="64" y1="43" x2="70" y2="43" />
          </g>
        )}

        {/* Facial hair (mustache/beard) */}
        {hasFacialHair && (
          <path
            d="M44 53 Q50 55 56 53 C54 55 46 55 44 53 Z"
            fill={hairColor}
            opacity="0.85"
          />
        )}

        {/* Headset for dispatchers/operators */}
        {accessory === 3 && (
          <g stroke="#873F46" strokeWidth="2" strokeLinecap="round">
            <path d="M30 45 C28 32 36 20 50 20 C64 20 72 32 70 45" fill="none" />
            <rect x="27" y="42" width="5" height="10" rx="2" fill="#542227" stroke="none" />
            <path d="M30 50 L38 58 L44 58" fill="none" strokeWidth="1.6" />
            <circle cx="44" cy="58" r="2" fill="#873F46" stroke="none" />
          </g>
        )}
      </svg>

      {/* Synthetic watermark tag */}
      <div className="absolute bottom-0 right-0 left-0 bg-[#873F46]/80 text-[7px] font-bold text-white tracking-widest uppercase text-center py-0.5 pointer-events-none backdrop-blur-xs">
        SYNTH
      </div>
    </div>
  );
};
