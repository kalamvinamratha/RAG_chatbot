import React from 'react';
import { ChartLineUp } from '@phosphor-icons/react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

interface BiomarkerChartProps {
  title?: string;
  data: Array<{
    date: string;
    value: number;
    referenceRange?: string;
    unit?: string;
  }>;
}

export const BiomarkerChart: React.FC<BiomarkerChartProps> = ({
  title = 'Clinical Biomarker Longitudinal Trend',
  data,
}) => {
  if (!data || data.length === 0) return null;

  return (
    <div className="bg-card  p-4 rounded-xl border border-border/90  my-3 shadow-xs transition-colors">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <ChartLineUp size={16} weight="duotone" className="text-primary " />
          <h4 className="text-xs font-semibold text-foreground  tracking-tight">{title}</h4>
        </div>
        {data[0]?.unit && (
          <span className="text-xs text-primary  font-mono font-semibold bg-secondary/40  px-2 py-0.5 rounded-md border border-primary/30 ">
            Unit: {data[0].unit}
          </span>
        )}
      </div>

      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="date"
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 'var(--ui-text-xs)', fill: 'var(--muted-foreground)' }}
            />
            <YAxis
              stroke="var(--muted-foreground)"
              tick={{ fontSize: 'var(--ui-text-xs)', fill: 'var(--muted-foreground)' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'var(--popover)',
                borderColor: 'var(--border)',
                color: 'var(--popover-foreground)',
                borderRadius: 'var(--radius-lg)',
                fontSize: 'var(--ui-text-xs)',
                boxShadow: 'var(--shadow-md)',
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--chart-1)"
              strokeWidth={2.5}
              dot={{ fill: 'var(--chart-2)', r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {data[0]?.referenceRange && (
        <div className="mt-2 text-xs text-muted-foreground  font-mono">
          Clinical Reference Range: {data[0].referenceRange}
        </div>
      )}
    </div>
  );
};
