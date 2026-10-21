import React from 'react';

interface CircularGaugeProps {
  value: number;
  max?: number;
  label: string;
  unit?: string;
  subtitle?: string;
  size?: number;
  strokeWidth?: number;
  color?: string;
  trackColor?: string;
  isPercentage?: boolean;
  tooltipText?: string;
}

export const CircularGauge: React.FC<CircularGaugeProps> = ({
  value,
  max = 10,
  label,
  unit = '',
  subtitle,
  size = 108,
  strokeWidth = 9,
  color = '#F43F4F',
  trackColor = '#2B3138',
  isPercentage = false,
  tooltipText,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clampedValue = Math.min(Math.max(value, 0), max);
  const percentage = (clampedValue / max) * 100;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const displayValue = isPercentage ? `${Math.round(clampedValue)}%` : clampedValue.toFixed(1);

  return (
    <div
      className="flex flex-col items-center text-center p-3.5 rounded-2xl bg-[#171B20] border border-[#2B3138] hover:border-[#3a4250] transition-colors"
      title={tooltipText || `${label}: ${displayValue}${unit || (isPercentage ? '' : `/${max}`)}`}
    >
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={trackColor}
            strokeWidth={strokeWidth}
            fill="none"
          />
          {/* Foreground Progress Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="none"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center Metric Text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-[20px] font-bold text-[#F5F5F5] leading-none tracking-tight">
            {displayValue}
          </span>
          <span className="text-[11px] font-semibold text-[#7E8995] mt-0.5">
            {unit || (isPercentage ? 'ratio' : `/${max}`)}
          </span>
        </div>
      </div>

      {/* Label and Explanatory Subtitle */}
      <div className="mt-2.5 max-w-[130px]">
        <span className="text-[13px] font-bold text-[#F5F5F5] block leading-tight">
          {label}
        </span>
        {subtitle && (
          <span className="text-[11px] text-[#7E8995] leading-tight block mt-0.5">
            {subtitle}
          </span>
        )}
      </div>
    </div>
  );
};

